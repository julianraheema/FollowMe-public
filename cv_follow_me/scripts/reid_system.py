# reid_system.py
import numpy as np
import config # Import the configuration

class ReIDSystem:
    """
    Manages person re-identification using multiple modalities,
    with optional dynamic weight calculation and dynamic Re-ID threshold calculation
    using a Leave-One-Out strategy for evaluating enrolled samples.
    """
    def __init__(self, feature_extractors_dict, modality_weights_config, reid_threshold_config_default):
        """
        Initializes the Re-ID system.

        Args:
            feature_extractors_dict (dict): Dictionary of active feature extractor instances.
            modality_weights_config (dict): Base modality weights from config.py.
            reid_threshold_config_default (float): Default Re-ID threshold from config.py.
        """
        self.feature_extractors = feature_extractors_dict
        self.base_modality_weights = modality_weights_config.copy()
        self.current_modality_weights = self.base_modality_weights.copy()
        
        self.default_reid_threshold = reid_threshold_config_default
        self.reid_threshold = self.default_reid_threshold # Active threshold

        # Stores features for each modality across all enrolled samples
        # e.g., {"RGB": [rgb_feat_sample1, rgb_feat_sample2,...], "Skeleton": [skel_feat_sample1, ...]}
        # These lists contain only valid, non-zero features.
        self.target_features = {mod_name: [] for mod_name in self.feature_extractors.keys()}
        
        # Stores all extracted features for each individual enrollment sample (can include None for failed modalities)
        # List of dicts: [{mod_name1: feat_vec_or_None, mod_name2: feat_vec_or_None}, {sample2_features}, ...]
        self.enrolled_samples_raw_features = []

        self.target_yolo_confidences = []
        
        self.is_target_enrolled_at_least_once = False
        self.dynamic_weights_calculated = False

        if config.PRINT_STATEMENTS:
            print("--- Re-ID System Initialized (DEBUG) ---")
            print(f"  Active Re-ID Modalities: {list(self.feature_extractors.keys())}")
            print(f"  Base Modality weights from config: {self.base_modality_weights}")
            print(f"  Default Re-ID threshold: {self.default_reid_threshold}")
            print(f"  Dynamic Weighting Enabled: {config.USE_DYNAMIC_WEIGHTING}")
            print(f"  Percentile Re-ID Threshold Enabled: {config.USE_PERCENTILE_REID_THRESHOLD}")
            if config.USE_PERCENTILE_REID_THRESHOLD:
                print(f"    Strategy: Leave-One-Out for enrolled sample scoring.")
                print(f"    Percentile: {config.REID_THRESHOLD_PERCENTILE*100:.0f}th (meaning boundary for top {(1.0-config.REID_THRESHOLD_PERCENTILE)*100:.0f}%)")
                print(f"    Min Samples for Percentile Calc: {config.MIN_SAMPLES_FOR_PERCENTILE_THRESHOLD}")
            print("----------------------------------------")

    def _cosine_similarity(self, vec1, vec2):
        if vec1 is None or vec2 is None or not hasattr(vec1, 'size') or not hasattr(vec2, 'size') or vec1.size == 0 or vec2.size == 0:
            return 0.0
        vec1_flat = vec1.flatten()
        vec2_flat = vec2.flatten()
        norm_vec1 = np.linalg.norm(vec1_flat)
        norm_vec2 = np.linalg.norm(vec2_flat)
        if norm_vec1 == 0 or norm_vec2 == 0:
            return 0.0
        dot_product = np.dot(vec1_flat, vec2_flat)
        similarity = dot_product / (norm_vec1 * norm_vec2)
        return max(0.0, similarity)

    def enroll_target_features_sample(self, modality_data_inputs, yolo_confidence_for_sample=None):
        sample_enrolled_this_time = False
        current_sample_extracted_features = {} 

        if config.PRINT_STATEMENTS:
            print(f"\nAttempting to enroll sample. Input keys: {list(modality_data_inputs.keys())}")

        for modality_name, extractor in self.feature_extractors.items():
            feature_vector = None
            input_data = modality_data_inputs.get(modality_name)

            if input_data is None and modality_name not in ["FaceRecognition"]:
                if config.PRINT_STATEMENTS: 
                    print(f"  Skipping enrollment for {modality_name}: No input data provided.")
                current_sample_extracted_features[modality_name] = None
                continue
            
            if modality_name == "FaceRecognition" and len(self.target_features.get("FaceRecognition", [])) > 0:
                if config.PRINT_STATEMENTS: 
                    print(f"  Skipping FaceRecognition enrollment (already have one sample). Using existing.")
                existing_face_feat = self.target_features["FaceRecognition"][0] if self.target_features.get("FaceRecognition") else None
                current_sample_extracted_features[modality_name] = existing_face_feat # Still log what this sample "would" use
                # sample_enrolled_this_time might still be true if other modalities contribute
                continue 
            
            try:
                if modality_name == "ForearmColor":
                    if input_data and "skeleton_joints_dict" in input_data and "rgb_image" in input_data:
                        feature_vector = extractor.extract_features(
                            input_data["skeleton_joints_dict"], input_data["rgb_image"], is_enrollment_phase=True)
                    else:
                        if config.PRINT_STATEMENTS: 
                            print(f"  Skipping ForearmColor enrollment: Missing data.")
                        feature_vector = None
                else:
                    feature_vector = extractor.extract_features(input_data, is_enrollment_phase=True)
            except Exception as e:
                print(f"ERROR: Feature extraction failed for {modality_name} during enrollment: {e}")
                feature_vector = None

            current_sample_extracted_features[modality_name] = feature_vector

            if feature_vector is not None and not np.all(feature_vector == 0):
                self.target_features[modality_name].append(feature_vector) # Add to the main gallery for this modality
                sample_enrolled_this_time = True 
                if config.PRINT_STATEMENTS:
                    print(f"  Enrolled feature for {modality_name}. Shape: {feature_vector.shape}. Gallery size now: {len(self.target_features[modality_name])}")
            elif config.PRINT_STATEMENTS:
                input_status = "None" if input_data is None else f"Type {type(input_data)}"
                if modality_name == "ForearmColor" and input_data:
                    input_status += f" (keys: {list(input_data.keys()) if isinstance(input_data, dict) else 'N/A'})"
                print(f"  No valid feature extracted for {modality_name} during enrollment. Input was: {input_status}. Feature was {type(feature_vector)}")
        
        if sample_enrolled_this_time: 
            self.is_target_enrolled_at_least_once = True
            if yolo_confidence_for_sample is not None:
                self.target_yolo_confidences.append(yolo_confidence_for_sample)
            self.enrolled_samples_raw_features.append(current_sample_extracted_features) # Add the dict of features for this sample
            if config.PRINT_STATEMENTS:
                print(f"Enrollment sample processed. One or more features added. Total distinct samples with features: {len(self.enrolled_samples_raw_features)}")
        else:
            if config.PRINT_STATEMENTS:
                print(f"Enrollment sample processed. No valid features extracted for any modality this round.")
        
        return sample_enrolled_this_time

    def _calculate_fused_score(self, query_features_dict, gallery_to_compare_against, weights_to_use):
        individual_modality_scores = {}
        fused_score_numerator = 0.0
        total_weight_denominator = 0.0

        for modality_name, query_feature in query_features_dict.items():
            current_mod_score = 0.0
            if modality_name not in self.feature_extractors or \
               query_feature is None or (hasattr(query_feature, 'size') and np.all(query_feature == 0)):
                individual_modality_scores[modality_name] = 0.0
                continue

            # Use the provided gallery_to_compare_against
            gallery_samples_for_mod = gallery_to_compare_against.get(modality_name, [])
            
            if gallery_samples_for_mod: 
                if modality_name == "FaceRecognition": 
                    if gallery_samples_for_mod: # Should contain one item for enrolled gallery if not LOO empty
                         target_ref_feature = gallery_samples_for_mod[0]
                         current_mod_score = self._cosine_similarity(query_feature, target_ref_feature)
                else:
                    max_sim = 0.0
                    for target_sample_feature in gallery_samples_for_mod:
                        sim = self._cosine_similarity(query_feature, target_sample_feature)
                        if sim > max_sim: max_sim = sim
                    current_mod_score = max_sim
            
            individual_modality_scores[modality_name] = current_mod_score
            weight = weights_to_use.get(modality_name, 0)

            if weight > 0 and gallery_samples_for_mod: 
                fused_score_numerator += weight * current_mod_score
                total_weight_denominator += weight
        
        normalized_fused_score = fused_score_numerator / total_weight_denominator if total_weight_denominator > 0 else 0.0
        return normalized_fused_score, individual_modality_scores

    def finalize_enrollment_phase(self):
        # 1. Calculate Dynamic Weights (if enabled)
        if config.USE_DYNAMIC_WEIGHTING and self.is_target_enrolled_at_least_once:
            unnormalized_dynamic_weights = {}
            avg_yolo_conf = np.mean(self.target_yolo_confidences) if self.target_yolo_confidences else 0.5
            if config.PRINT_STATEMENTS: 
                print(f"ReID: Avg YOLO conf for dynamic weights: {avg_yolo_conf:.3f}")

            for modality_name, base_weight in self.base_modality_weights.items():
                if modality_name not in self.feature_extractors:
                    unnormalized_dynamic_weights[modality_name] = 0.0
                    continue
                
                reliability_factor = config.DEFAULT_RELIABILITY_FACTOR_NO_SAMPLES
                # Use self.target_features for variance calculation as it contains only valid features
                feature_samples_for_mod_variance = self.target_features.get(modality_name, [])

                if len(feature_samples_for_mod_variance) >= config.MIN_SAMPLES_FOR_VARIANCE_WEIGHTING:
                    # No need to filter for None/zeros here as self.target_features only has valid ones
                    if len(feature_samples_for_mod_variance) >= config.MIN_VALID_SAMPLES_FOR_RELIABILITY: # Should be same
                        stacked_features = np.vstack(feature_samples_for_mod_variance)
                        if stacked_features.shape[0] == 1: mean_variance = config.MAX_VARIANCE_FOR_WEIGHTING
                        else:
                            variances_per_dim = np.var(stacked_features, axis=0)
                            finite_variances = variances_per_dim[np.isfinite(variances_per_dim)]
                            mean_variance = np.mean(finite_variances) if finite_variances.size > 0 else 0.0
                        reliability_factor = 1.0 / (mean_variance + 1e-6)  # Add small epsilon to avoid division by zero
                        if config.PRINT_STATEMENTS: 
                            print(f"  ReID DW ({modality_name}): MeanVar={mean_variance:.4e}, ReliabilityFactor={reliability_factor:.4e}")
                    elif config.PRINT_STATEMENTS: 
                        print(f"  ReID DW ({modality_name}): Not enough valid samples for variance.")
                elif config.PRINT_STATEMENTS: 
                    print(f"  ReID DW ({modality_name}): Not enough total samples for variance.")
                unnormalized_dynamic_weights[modality_name] = base_weight * reliability_factor
            
            if config.YOLO_CONFIDENCE_MODULATION_POWER > 0 and avg_yolo_conf > 0:
                confidence_multiplier = avg_yolo_conf ** config.YOLO_CONFIDENCE_MODULATION_POWER
                for mod_name in unnormalized_dynamic_weights: unnormalized_dynamic_weights[mod_name] *= confidence_multiplier
            
            total_unnormalized_weight = sum(unnormalized_dynamic_weights.values())
            if total_unnormalized_weight > 0:
                self.current_modality_weights = {m: w / total_unnormalized_weight for m, w in unnormalized_dynamic_weights.items()}
                self.dynamic_weights_calculated = True
                if config.PRINT_STATEMENTS: 
                    print(f"ReID: Dynamic weights calculated: { {k: round(v,3) for k,v in self.current_modality_weights.items()} }")
            else:
                self.current_modality_weights = self.base_modality_weights.copy()
                self.dynamic_weights_calculated = False
                if config.PRINT_STATEMENTS: 
                    print("ReID: Dynamic weight sum is zero. Using base weights.")
        else:
            self.current_modality_weights = self.base_modality_weights.copy()
            self.dynamic_weights_calculated = False
            if config.PRINT_STATEMENTS and config.USE_DYNAMIC_WEIGHTING: 
                print("ReID: Dynamic weighting skipped. Using base weights.")

        # 2. Calculate Percentile-based Re-ID Threshold (if enabled) using Leave-One-Out
        if config.USE_PERCENTILE_REID_THRESHOLD and self.is_target_enrolled_at_least_once:
            if len(self.enrolled_samples_raw_features) < config.MIN_SAMPLES_FOR_PERCENTILE_THRESHOLD:
                if config.PRINT_STATEMENTS:
                    print(f"ReID: Not enough enrolled samples ({len(self.enrolled_samples_raw_features)}) for LOO percentile threshold. Min: {config.MIN_SAMPLES_FOR_PERCENTILE_THRESHOLD}. Using default: {self.default_reid_threshold:.4f}")
                self.reid_threshold = self.default_reid_threshold
            else:
                fused_scores_for_enrolled_samples = []
                if config.PRINT_STATEMENTS: 
                    print(f"ReID: Calculating LOO fused scores for {len(self.enrolled_samples_raw_features)} enrolled samples for threshold...")
                
                for i, sample_features_dict_i in enumerate(self.enrolled_samples_raw_features):
                    # Construct Leave-One-Out gallery for this sample S_i
                    loo_gallery_for_this_sample_i = {}
                    for mod_name_gallery, all_gallery_features_for_mod in self.target_features.items():
                        # feature_from_S_i is the specific feature vector from sample_features_dict_i for this mod_name_gallery
                        feature_from_S_i = sample_features_dict_i.get(mod_name_gallery)
                        
                        temp_loo_mod_gallery = list(all_gallery_features_for_mod) # Start with a copy of full gallery for this mod
                        
                        if feature_from_S_i is not None and not np.all(feature_from_S_i == 0):
                            # Attempt to remove the first instance of feature_from_S_i from temp_loo_mod_gallery
                            removed = False
                            for idx, feat_in_gallery in enumerate(temp_loo_mod_gallery):
                                if np.array_equal(feat_in_gallery, feature_from_S_i):
                                    del temp_loo_mod_gallery[idx]
                                    removed = True
                                    break 
                        
                        loo_gallery_for_this_sample_i[mod_name_gallery] = temp_loo_mod_gallery

                    fused_score, individual_scores_for_sample = self._calculate_fused_score(
                        sample_features_dict_i,         # Query is S_i's features
                        loo_gallery_for_this_sample_i,  # Gallery is S_all excluding S_i's contribution
                        self.current_modality_weights
                    )
                    fused_scores_for_enrolled_samples.append(fused_score)
                    if config.PRINT_STATEMENTS: 
                        scores_str = ", ".join([f"{mod[:3]}:{score:.2f}" for mod, score in individual_scores_for_sample.items() if self.current_modality_weights.get(mod,0)>0]) # Show only weighted
                        print(f"  ReID LOO-ThreshCalc: Sample {i} Fused Score = {fused_score:.4f} (Indiv Weighted: {scores_str})")

                if fused_scores_for_enrolled_samples:
                    percentile_to_calc = (1.0 - config.REID_THRESHOLD_PERCENTILE) * 100.0
                    calculated_threshold = np.percentile(fused_scores_for_enrolled_samples, percentile_to_calc)
                    self.reid_threshold = max(calculated_threshold, 0.0) 
                    if config.PRINT_STATEMENTS:
                        print(f"ReID: Dynamic LOO Re-ID threshold calculated from {len(fused_scores_for_enrolled_samples)} scores.")
                        print(f"  LOO Scores: {[round(s, 3) for s in sorted(fused_scores_for_enrolled_samples)]}")
                        print(f"  Percentile used: {percentile_to_calc:.1f}th (for 'top {config.REID_THRESHOLD_PERCENTILE*100:.0f}%' config)")
                        print(f"  New Re-ID Threshold: {self.reid_threshold:.4f}")
                else:
                    if config.PRINT_STATEMENTS: 
                        print("ReID: No LOO fused scores calculated. Using default threshold.")
                    self.reid_threshold = self.default_reid_threshold
        else: 
            self.reid_threshold = self.default_reid_threshold
            if config.PRINT_STATEMENTS:
                state_reason = "disabled in config" if not config.USE_PERCENTILE_REID_THRESHOLD else "target not enrolled"
                print(f"ReID: Percentile threshold calculation skipped ({state_reason}). Using default: {self.default_reid_threshold:.4f}")


    def re_identify(self, query_modality_data_inputs):
        if not self.is_target_enrolled_at_least_once:
            if config.PRINT_STATEMENTS: 
                print("Re-ID attempt failed: Target not enrolled.")
            return False, 0.0, {}

        query_features_dict = {}
        if config.PRINT_STATEMENTS: 
            print(f"\nRe-identifying query. Input keys for extraction: {list(query_modality_data_inputs.keys())}")
        for modality_name, extractor in self.feature_extractors.items():
            query_feature_for_mod = None 
            query_input_for_mod = query_modality_data_inputs.get(modality_name)
            
            if modality_name == "FaceRecognition":
                query_feature_for_mod = extractor.extract_features(query_input_for_mod, is_enrollment_phase=False)
            elif query_input_for_mod is not None: 
                try:
                    if modality_name == "ForearmColor":
                         if query_input_for_mod and "skeleton_joints_dict" in query_input_for_mod and "rgb_image" in query_input_for_mod:
                            query_feature_for_mod = extractor.extract_features(
                                query_input_for_mod["skeleton_joints_dict"], query_input_for_mod["rgb_image"], is_enrollment_phase=False)
                    else:
                        query_feature_for_mod = extractor.extract_features(query_input_for_mod, is_enrollment_phase=False)
                except Exception as e:
                    print(f"ERROR: Query feature extraction failed for {modality_name}: {e}")
                    query_feature_for_mod = None
            
            query_features_dict[modality_name] = query_feature_for_mod
            if config.PRINT_STATEMENTS and query_feature_for_mod is not None and not np.all(query_feature_for_mod == 0) :
                print(f"  ReID Query Extracted for {modality_name}, Shape: {query_feature_for_mod.shape if hasattr(query_feature_for_mod, 'shape') else 'N/A'}")
            elif config.PRINT_STATEMENTS and (query_feature_for_mod is None or (hasattr(query_feature_for_mod, 'size') and np.all(query_feature_for_mod == 0))):
                 print(f"  ReID Query Extraction for {modality_name}: No valid feature (None or Zeros).")

        weights_to_use = self.current_modality_weights if self.dynamic_weights_calculated and config.USE_DYNAMIC_WEIGHTING else self.base_modality_weights
        if config.PRINT_STATEMENTS:
            print(f"  ReID: Using {'DYNAMIC' if self.dynamic_weights_calculated and config.USE_DYNAMIC_WEIGHTING else 'BASE (or normalized base)'} weights: { {k: round(v,3) for k,v in weights_to_use.items()} }")

        normalized_fused_score, individual_modality_scores = self._calculate_fused_score(
            query_features_dict,
            self.target_features, # Compare against the full gallery for actual Re-ID
            weights_to_use
        )

        is_match = normalized_fused_score >= self.reid_threshold

        if config.PRINT_STATEMENTS:
            print(f"Re-ID Result: Fused Score = {normalized_fused_score:.4f}, Active Threshold = {self.reid_threshold:.4f}, Match = {is_match}")
            # Filter individual_scores to show only those from weighted modalities
            weighted_indiv_scores = {mod: score for mod, score in individual_modality_scores.items() if weights_to_use.get(mod, 0) > 0}
            print(f"  Individual Weighted Scores: { {k: f'{v:.4f}' for k, v in weighted_indiv_scores.items()} }")
        return is_match, normalized_fused_score, individual_modality_scores

    def reset_enrollment(self):
        for mod_name in self.target_features:
            self.target_features[mod_name] = []
        
        self.enrolled_samples_raw_features = [] 
        self.target_yolo_confidences = []
        self.is_target_enrolled_at_least_once = False
        
        self.current_modality_weights = self.base_modality_weights.copy() 
        self.dynamic_weights_calculated = False
        
        self.reid_threshold = self.default_reid_threshold 
        
        if config.PRINT_STATEMENTS:
            print("\nRe-ID System enrollment gallery, raw samples, dynamic weights, and Re-ID threshold have been reset.")

    def get_is_target_enrolled(self):
        return self.is_target_enrolled_at_least_once

    def get_enrollment_count(self): # Returns number of multi-modal sample sets processed
        return len(self.enrolled_samples_raw_features)
#vision_utils.py

import numpy as np
import cv2
import rospy # For logging within these utils if necessary
import face_recognition # If _match_yolo_to_face is moved here

def convert_box_to_cxcywh(box):
    """Converts [x1, y1, x2, y2] box to [cx, cy, w, h]."""
    x1, y1, x2, y2 = box
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    w = x2 - x1
    h = y2 - y1
    return cx, cy, w, h

def get_median_depth_in_box_mm(raw_depth_image, box_coords):
    """Calculates the median depth within a bounding box from a raw depth image."""
    if raw_depth_image is None:
        return None
    x1, y1, x2, y2 = map(int, box_coords)
    h_img, w_img = raw_depth_image.shape[:2]

    x1_c, y1_c = max(0, x1), max(0, y1)
    x2_c, y2_c = min(w_img, x2), min(h_img, y2)

    if x1_c >= x2_c or y1_c >= y2_c:
        return None

    try:
        depth_roi = raw_depth_image[y1_c:y2_c, x1_c:x2_c]
        valid_depths = depth_roi[depth_roi > 0]
        return np.median(valid_depths) if valid_depths.size > 0 else None
    except Exception as e:
        rospy.logerr(f"Error in get_median_depth_in_box_mm: {e}")
        return None

def deproject_pixel_to_point_m(fx, fy, cx, cy, pixel_x, pixel_y, depth_mm):
    """Deprojects a 2D pixel with depth to a 3D point in camera coordinates (meters)."""
    if any(v is None for v in [fx, fy, cx, cy, depth_mm]) or depth_mm <= 0:
        return None, None, None
    try:
        depth_m = float(depth_mm) / 1000.0
        cam_x = (float(pixel_x) - cx) * depth_m / fx
        cam_y = (float(pixel_y) - cy) * depth_m / fy
        return cam_x, cam_y, depth_m
    except Exception as e:
        rospy.logerr(f"Error in deproject_pixel_to_point_m: {e}")
        return None, None, None

def match_yolo_to_face(yolo_box, frame_face_locations_scaled, frame_face_encodings, scale_factor, logger=rospy):
    """Matches a YOLO detection box to a detected face within it."""
    if not frame_face_locations_scaled or not frame_face_encodings:
        return None

    yolo_x1, yolo_y1, yolo_x2, yolo_y2 = yolo_box
    yolo_center_x, yolo_center_y = (yolo_x1 + yolo_x2) / 2, (yolo_y1 + yolo_y2) / 2

    best_match_encoding = None
    min_center_dist_sq = float('inf')

    for i, (top_s, right_s, bottom_s, left_s) in enumerate(frame_face_locations_scaled):
        if scale_factor == 0:
            return None # Avoid division by zero
        left, top, right, bottom = left_s / scale_factor, top_s / scale_factor, right_s / scale_factor, bottom_s / scale_factor

        if left < yolo_center_x < right and top < yolo_center_y < bottom:
            face_center_x, face_center_y = (left + right) / 2, (top + bottom) / 2
            dist_sq = (yolo_center_x - face_center_x)**2 + (yolo_center_y - face_center_y)**2
            if dist_sq < min_center_dist_sq:
                min_center_dist_sq = dist_sq
                if i < len(frame_face_encodings):
                    best_match_encoding = frame_face_encodings[i]
                else:
                    logger.logwarn("_match_yolo_to_face: Mismatch between face_locations and face_encodings length.")
                    best_match_encoding = None
    return best_match_encoding

def calculate_iou(box_a, box_b):
    """Calculate Intersection over Union (IoU) of two bounding boxes.
    Boxes are (x1, y1, x2, y2).
    Returns 0.0 if there is no overlap or if areas are 0.
    """
    # Determine the (x, y)-coordinates of the intersection rectangle
    x_a = max(box_a[0], box_b[0])
    y_a = max(box_a[1], box_b[1])
    x_b = min(box_a[2], box_b[2])
    y_b = min(box_a[3], box_b[3])

    # Compute the area of intersection rectangle
    # Ensure x_b > x_a and y_b > y_a for valid intersection
    inter_width = x_b - x_a
    inter_height = y_b - y_a

    if inter_width <= 0 or inter_height <= 0:
        return 0.0
    
    inter_area = inter_width * inter_height

    # Compute the area of both bounding boxes
    box_a_area = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    box_b_area = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])

    if box_a_area <= 0 or box_b_area <= 0: # Avoid division by zero if a box has no area
        return 0.0

    # Compute the union area
    union_area = float(box_a_area + box_b_area - inter_area)

    if union_area == 0: # Avoid division by zero
        return 0.0
        
    iou = inter_area / union_area
    return iou
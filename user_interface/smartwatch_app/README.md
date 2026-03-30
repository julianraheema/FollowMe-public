
## FollowMeApp - An Android Studio SmartWatch Application 

FollowMe is a Wear OS SmartWatch application built using Java+Kotlin in Android Studio. It is designed to provide wearable technology for seamless human-robot interaction. 
Furthermore, it enables the wearer (users) to connect to a robot and control it via an intuitive interface with a color-blind-friendly palette and easy-to-see icons. In all, 
the application offers user's flexibility, functionality, and simplicity. 

# Features 
- Robot connection 
- Smartwatch Support
- Intuitive Layout 
- Color-Blind Friendly Palette
- Simple and lightweight functionality 

# Requirements
- [Android Studio](https://developer.android.com/studio?gad_source=1&gad_campaignid=22552041772&gbraid=0AAAAAC-IOZne-64nIukeW4hKEjRtw2H4W&gclid=Cj0KCQjw0erBBhDTARIsAKO8iqQHAcpII_VXCVwXBNbzwsFn4gdAdRiTWq2T5LVBufGb2Gbe6RIqoD4aAhAkEALw_wcB&gclsrc=aw.ds)
- [Java 23 or less](https://www.oracle.com/java/technologies/javase/jdk23-archive-downloads.html)
- Gradle 8.0 or later
- A physical Wear OS smartwatch or a virtual Wear OS emulator 

# How to run this virtually 
1. Open Android Studio 
- Launch Android Studio 
- Select **Clone Repository**
- Navigate to the cloned folder and open it 
- Sync Gradle Automatically
2. Set Up the WearOS Emulator
- Navigate to **Tools > Device Manager** 
- Select **"Add A New Device"**
- Click **"Create Virtual Device"** and **WearOS**
- Select **Wear OS Large Round** 
- Navigate to **Next** and **Finish**
3. Run the application
- Click the **Run** button in Android Studio toolbar
- Select the Wear OS emulator you just created 
- Wait for the application to build and deploy
- The application should connect and launch on the smartwatch screen
- 
# How to run this physically
1. Activate developer mode 
2. Go to `setting/aboutme/software information/software version/` and tap 7 times until the message says **developer mode active**
3. Go to developer mode then select wifi debugging, turn on, and allow
4. Ensure the smartwatch and the computer are connected on the same Wi-Fi network
5. On the computer the android studio code is hosted, go to the terminal, complete the **adb pair ip:port** on the smartwatch click pair code, and **ip:port**
6. Then complete it with `adb connect ip:port`

# Core Project Components
- Java+Kotlin Source Code **(MainActivity.kt)**
- - A file that contains the source code for the user interaction and sending information to control the robot
- UI Layout Values **(res/)**
- - A directory that contains all users-interface resources such as images, XML files, and more 
- - Build Configuration **(build.gradle.kts)**
- - Defines the project's build properties such as dependencies, plugins, and more

# Interaction Capabilities 
1. Welcome Page
- Select **Claim** and **PowerOn** to create a connection between the user and robot
2. Command Page 
- For simple control, select **Sit/Stand** or **Dock/Undock** to trigger actions on the robot
- For more advanced control, select **Teleop** or **Follower** to trigger movement and following capabilities on the robot
3. Teleop Mode 
- If **Teleop** is selected, the application will navigate to a new page with controls
- This new page will allow directional movement on the robot such as up, down, right, left, and rotational movement
4. Follower Mode 
- If **Follower** is selected, the application will navigate to a new page where the robot can follow the user
- Currently, there are two follower modes: 
- - QR Follower: Follows a user based on a visible and level QR marker
- - CV Follower: Follows a user using computer vision to track and follow their movement 
5. eStop Mode 
- If any functionality breaks down, a user can select the eStop button to freeze movement completely

# Future Tasks 
1. Create the functionality for the welcome page interface to say **"power off and unclaim"** when the user is done
2. When selecting a particular **follower-mode** add a color feature. Allow the color of the selected follower button to change so the user can see it was selected
3. Remove hard-coded computer vision follower timer
4. Add a wait feature for the **power-on** and **claim** button
5. Include the current status of the robot's battery life
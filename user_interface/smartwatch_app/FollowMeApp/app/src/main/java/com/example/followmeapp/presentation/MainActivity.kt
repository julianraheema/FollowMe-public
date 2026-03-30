/* While this template provides a good starting point for using Wear Compose, you can always
 * take a look at https://github.com/android/wear-os-samples/tree/main/ComposeStarter to find the
 * most up to date changes to the libraries and their usages.
 */

package com.example.followmeapp.presentation

import android.R
import android.os.Bundle
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.forEachGesture
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.wrapContentSize
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.ArrowCircleLeft
import androidx.compose.material.icons.filled.ArrowCircleRight
import androidx.compose.material.icons.filled.ArrowDownward
import androidx.compose.material.icons.filled.ArrowForward
import androidx.compose.material.icons.filled.ArrowUpward
import androidx.compose.material.icons.filled.Bluetooth
import androidx.compose.material.icons.filled.Camera
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Dangerous
import androidx.compose.material.icons.filled.FlashOff
import androidx.compose.material.icons.filled.FlashOn
import androidx.compose.material.icons.filled.KeyboardDoubleArrowDown
import androidx.compose.material.icons.filled.KeyboardDoubleArrowUp
import androidx.compose.material.icons.filled.LocationOff
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.filled.Merge
import androidx.compose.material.icons.filled.PersonAdd
import androidx.compose.material.icons.filled.QrCode
import androidx.compose.material.icons.filled.RemoveCircle
import androidx.compose.material.icons.filled.RotateLeft
import androidx.compose.material.icons.filled.RotateRight
import androidx.compose.material.icons.filled.Sensors
import androidx.compose.material.icons.filled.SportsEsports
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.wear.compose.material.Button
import androidx.wear.compose.material.ButtonDefaults
import androidx.wear.compose.material.Icon
import androidx.wear.compose.material.Text
import androidx.wear.tooling.preview.devices.WearDevices
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.net.HttpURLConnection
import java.net.URL
import java.nio.file.WatchEvent

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()

        super.onCreate(savedInstanceState)

        setTheme(R.style.Theme_DeviceDefault)

        setContent {
            WearApp()
        }
    }
}

/*
    sendCommand: the function will send a string command to server.py
    which signals the robot to perform such action
*/
fun sendCommand(action: String, page: String) {
    CoroutineScope(Dispatchers.IO).launch {
        try {
            val serverUrl = "http://172.20.10.5:5000/post_action"
            val url = URL(serverUrl)
            val connection = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
            }

            val jsonBody = """{"action":"$action"}"""
            connection.outputStream.use { os ->
                os.write(jsonBody.toByteArray(Charsets.UTF_8))
            }

            val responseCode = connection.responseCode
            Log.d(page, "Sent JSON `$jsonBody` — response: $responseCode")
        } catch (e: Exception) {
            Log.e(page, "HTTP error: ${e.message}", e)
        }
    }
}

@Composable
fun WearApp() {
    val navController = rememberNavController()
    val viewModel: MyViewModel = viewModel()
    NavHost(navController = navController, startDestination = "main") {
        composable("main") {
            CommandAndControl(navController, viewModel)
        }
        composable("commands") {
            Commands(navController, viewModel)
        }
        composable("teleop") {
            TeleopScreen(navController, viewModel)
        }
        composable("follower") {
            FollowerScreen(navController, viewModel)
        }
        composable("eStop"){
            StopScreen(navController)
        }
        composable("cvFollower") {
            ComputerVisionFollower(navController, viewModel)
        }

        composable("cvTimer") {
            ComputerVisionTimer(navController)
        }
    }
    }

/*
    MyViewModel: is a class that allows the application to hold the state of each button
    while exploring different pages.
 */
class MyViewModel: ViewModel(){
    var isClaimed by mutableStateOf(true)
    var isPowered by mutableStateOf(true)
    var isSitting by mutableStateOf(true)
    var isDocked  by mutableStateOf(true)
    var isCVFollower by mutableStateOf(true)
    var isBTFollower by mutableStateOf(true)
    var isFFollower  by mutableStateOf(true)
    var isEStop by mutableStateOf(true)
}

/*
    CommandAndControl: a function that powers on and connects the robot to the
    smartwatch device.
 */
@Composable
fun CommandAndControl(navController: NavHostController, viewModel:MyViewModel = viewModel()) {
    var isClaimed = viewModel.isClaimed
    var isEStop   = viewModel.isEStop
    var counter by remember { mutableStateOf(0) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(4.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        Spacer(modifier = Modifier.height(10.dp))
        // Text - Information to welcome the user & future implementation will have information to say goodbye to the user
        Text(text = "Welcome", style = TextStyle(fontSize = 4.em))
        Text(text = "Select claim and power on to connect.", style = TextStyle(fontSize = 1.8.em))
        //  add functionality later --> Text(text = "Select power off and unclaim to disconnect.", style = TextStyle(fontSize = 1.7.em))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceEvenly
        ) {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                // Button: Claim/Release Button to start the robot
                Button(onClick = {
                    print(isClaimed)
                    val action = if (isClaimed) "claim" else "release"
                    sendCommand(action, "CommandAndControl")
                    viewModel.isClaimed = !isClaimed
                    if (viewModel.isClaimed && !viewModel.isPowered) viewModel.isPowered = true
                }, modifier = Modifier.size(200.dp, 42.dp),
                    colors  = if (isClaimed) ButtonDefaults.buttonColors(Color(red=16, green=101, blue=171)) else ButtonDefaults.buttonColors(Color(0xFFdc267f)),
                    border  = if (isClaimed) ButtonDefaults.buttonBorder(borderStroke = BorderStroke(1.5.dp, Color(0xFF7df9ff))) else ButtonDefaults.buttonBorder(borderStroke = BorderStroke(1.5.dp, Color(0xffffdde6)))
                ){
                    Row(modifier = Modifier.fillMaxWidth().padding(10.dp),
                        horizontalArrangement = Arrangement.Start,
                        verticalAlignment = Alignment.CenterVertically) {
                        if (isClaimed) Icon(Icons.Filled.CheckCircle, contentDescription = "on", tint = Color(0xFF7df9ff), modifier = Modifier.size(38.dp).scale(1.5f)) else Icon(Icons.Filled.RemoveCircle, contentDescription = "off", tint = Color(0xffffdde6), modifier = Modifier.size(38.dp).scale(1.5f))
                    }
                    Text(text = if (isClaimed) "Claim" else "Release",
                        color = Color.White,
                        style =  TextStyle(fontSize = 4.em))
                }
                // Button: Power On/Off Button to connect the robot to the smartwatch application
                Button(onClick = {
                    val action = if (!viewModel.isPowered) "poweroff" else "poweron"
                    sendCommand(action, "CommandAndControl")
                    if (!isClaimed) viewModel.isPowered = !viewModel.isPowered},
                    modifier = Modifier.size(200.dp, 42.dp),
                    colors   = if (!viewModel.isPowered) ButtonDefaults.buttonColors(Color(0xFFdc267f)) else ButtonDefaults.buttonColors(Color(red=16, green=101, blue=171)),
                    border   = if (!viewModel.isPowered) ButtonDefaults.buttonBorder(borderStroke = BorderStroke(1.5.dp, Color(0xffffdde6))) else ButtonDefaults.buttonBorder(borderStroke = BorderStroke(1.5.dp, Color(0xFF7df9ff)))
                ) {
                    Row(modifier = Modifier.fillMaxWidth().padding(10.dp),
                        horizontalArrangement = Arrangement.Start,
                        verticalAlignment = Alignment.CenterVertically) {
                        if (!viewModel.isPowered)  Icon(Icons.Filled.FlashOff, contentDescription = "off", tint = Color(0xffffdde6), modifier = Modifier.size(38.dp).scale(1.5f)) else Icon(Icons.Filled.FlashOn, contentDescription = "on", tint = Color(0xFF7df9ff), modifier = Modifier.size(38.dp).scale(1.5f))
                    }
                    Text(text = if (!viewModel.isPowered) "Power Off" else "Power On",
                        color = Color.White,
                        style =  TextStyle(fontSize = 4.em))
                }

                // Counter Variable Increment: functionality to display the eStop & next button after the first time claim & power on is selected
                if(!viewModel.isPowered && !viewModel.isClaimed) counter += 1

                if (counter > 0 && !viewModel.isPowered && !viewModel.isClaimed) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.Center
                    ) {
                        // Button: Next button to start next page (commands)
                        Button(
                            onClick  = { navController.navigate("commands")},
                            shape    = RoundedCornerShape(50),
                            modifier = Modifier.size(40.dp, 40.dp)
                                .shadow(elevation = 12.dp,
                                    shape = RoundedCornerShape(50)),
                            colors = ButtonDefaults.buttonColors(Color(0xff525252)),
                        ){
                            Icon(Icons.Filled.ArrowCircleRight, contentDescription = "forward", tint= Color.White, modifier = Modifier.size(25.dp).scale(1.5f))
                        }

                        Spacer(modifier = Modifier.width(23.dp))
                        // Button: Freeze Button to pause the robot in any state of action
                        Button(
                            onClick  = {
                                val action = "freeze"
                                sendCommand(action, "CommandAndControl")
                                viewModel.isEStop = !isEStop
                                navController.navigate("eStop")},
                            shape    = RoundedCornerShape(50),
                            modifier = Modifier.size(40.dp, 40.dp)
                                .shadow(elevation = 12.dp,
                                    shape = RoundedCornerShape(50)),
                            colors = ButtonDefaults.buttonColors(Color(0xfffa4d56)),
                        ){
                            Icon(Icons.Filled.Dangerous, contentDescription = "sit", tint= Color.White, modifier = Modifier.size(25.dp).scale(1.5f))
                        }
                    }
                }
            }
        }
    }
}

/*
    Commands: a function that provides simple commands and advanced commands to the robot
 */
@Composable
fun Commands(navController: NavController, viewModel:MyViewModel = viewModel()) {
    var isSitting = viewModel.isSitting
    var isDocked  = viewModel.isDocked
    var isEStop   = viewModel.isEStop

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(10.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Spacer(modifier = Modifier.height(25.dp))
        Text(
            text = "Standard Controls",
            modifier = Modifier.padding(bottom = 10.dp),
            style =  TextStyle(fontSize = 3.em)
        )
       Row (
           modifier = Modifier.fillMaxWidth(),
           horizontalArrangement = Arrangement.Center
       ) {
           // Button: Sit/Stand Button to allow the robot to sit or stand (the default is sit)
           Button(onClick = {
               val action = if (!isSitting) "sit" else "stand"
               sendCommand(action, "Commands")
               viewModel.isSitting = !isSitting
           }, modifier = Modifier.size(100.dp, 35.dp),
               colors  = if (isSitting) ButtonDefaults.buttonColors(Color(0xFF785ef0)) else ButtonDefaults.buttonColors(Color(0xffffb000)),
               border  = if (isSitting) ButtonDefaults.buttonBorder(borderStroke = BorderStroke(2.dp, Color(0xffe9a7ff))) else ButtonDefaults.buttonBorder(borderStroke = BorderStroke(2.dp, Color(0xffffffc1)))
           ){
               Text(text = if (!isSitting) "Sit" else "Stand",
                   color = Color.White,
                   style =  TextStyle(fontSize = 2.7.em))
               Row(modifier = Modifier.fillMaxWidth().padding(2.dp),
                   horizontalArrangement = Arrangement.Start,
                   verticalAlignment = Alignment.CenterVertically) {
                   if (!isSitting) Icon(Icons.Filled.KeyboardDoubleArrowDown, tint = Color(0xffffffc1), contentDescription = "sit",  modifier = Modifier.size(21.dp).scale(1.2f)) else Icon(Icons.Filled.KeyboardDoubleArrowUp, tint = Color(0xffe9a7ff), contentDescription = "stand", modifier = Modifier.size(21.dp).scale(1.2f))
               }
           }

           Spacer(modifier = Modifier.width(4.dp))

           // Button: Dock/Undock Button to send the robot home or not
           Button(onClick = {
               val action = if (isDocked) "dock" else "undock"
               sendCommand(action, "Commands")
               viewModel.isDocked = !isDocked
           }, modifier = Modifier.size(100.dp, 35.dp),
               colors  = if (isDocked) ButtonDefaults.buttonColors(Color(0xFF785ef0)) else ButtonDefaults.buttonColors(Color(0xffffb000)),
               border  = if (isDocked) ButtonDefaults.buttonBorder(borderStroke = BorderStroke(2.dp, Color(0xffe9a7ff))) else ButtonDefaults.buttonBorder(borderStroke = BorderStroke(2.dp, Color(0xffffffc1)))
           ){
               Text(text = if (isDocked) "Dock" else "Undock", color = Color.White, style = TextStyle(fontSize = 2.7.em))
               Row(modifier = Modifier.fillMaxWidth().padding(2.dp),
                   horizontalArrangement = Arrangement.Start,
                   verticalAlignment = Alignment.CenterVertically) {
                   if (isDocked) Icon(Icons.Filled.LocationOn, contentDescription = "dock", tint= Color(0xffe9a7ff), modifier = Modifier.size(21.dp).scale(1f)) else Icon(Icons.Filled.LocationOff, contentDescription = "stand", tint = Color(0xffffffc1), modifier = Modifier.size(21.dp).scale(1f))
               }
           }
       }

        Spacer(modifier = Modifier.height(10.dp))

        Text(
            text = "Advanced Controls",
            modifier = Modifier.padding(bottom = 5.dp),
            style =  TextStyle(fontSize = 3.em)
        )
        Row (
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.Center
        ) {
            // Button: Teleop button to send to a new page to move the robot in any direction
            Button(onClick = {
                sendCommand("teleop", "Commands")
                navController.navigate("teleop")
            },  modifier = Modifier.size(100.dp, 35.dp),
                colors   = ButtonDefaults.buttonColors(Color(0xFF785ef0)),
                border   = ButtonDefaults.buttonBorder(borderStroke = BorderStroke(2.dp, Color(0xffe9a7ff)))
            ){
                Text(text = "Teleop", color = Color.White, style = TextStyle(fontSize = 2.7.em))
                Row(modifier = Modifier.fillMaxWidth().padding(2.dp),
                    horizontalArrangement = Arrangement.Start,
                    verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Filled.SportsEsports, contentDescription = "sit", tint= Color(0xffe9a7ff), modifier = Modifier.size(21.dp).scale(1f))
                }
            }

            Spacer(modifier = Modifier.width(4.dp))

            // Button: Follower button to send to a new page to provide different follower modes with the robot
            Button(onClick = {
                sendCommand("follower", "Commands")
                navController.navigate("follower")
            }, modifier = Modifier.size(100.dp, 35.dp),
                colors  = ButtonDefaults.buttonColors(Color(0xFF785ef0)),
                border  = ButtonDefaults.buttonBorder(borderStroke = BorderStroke(2.dp, Color(0xffe9a7ff)))
            ){
                Text(text = "Follow", color = Color.White, style = TextStyle(fontSize = 2.7.em))
                Row(modifier = Modifier.fillMaxWidth().padding(2.dp),
                    horizontalArrangement = Arrangement.Start,
                    verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Filled.PersonAdd, contentDescription = "sit",tint= Color(0xffe9a7ff), modifier = Modifier.size(21.dp).scale(1f))
                }
            }
        }

        Spacer(modifier = Modifier.height(5.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.Center
        ) {

            Spacer(modifier = Modifier.height(40.dp))

            // Button: Back button to go back to the previous page & turn-off connection
            Button(
                onClick  = { navController.popBackStack()},
                shape    = RoundedCornerShape(50),
                modifier = Modifier.size(38.dp, 38.dp)
                    .shadow(elevation = 12.dp,
                            shape = RoundedCornerShape(50)),
                colors = ButtonDefaults.buttonColors(Color(0xff525252)),
                ){
                Icon(Icons.Filled.ArrowCircleLeft, contentDescription = "back", tint= Color.White, modifier = Modifier.size(25.dp).scale(1.5f))
            }

            Spacer(modifier = Modifier.width(32.dp))

            // Button: Freeze button to pause the robot in any state of action
            Button(
                onClick  = {
                    val action = "freeze"
                    sendCommand(action, "Commands")
                    viewModel.isEStop = !isEStop
                    navController.navigate("eStop")},
                shape    = RoundedCornerShape(50),
                modifier = Modifier.size(38.dp, 38.dp)
                    .shadow(elevation = 12.dp,
                        shape = RoundedCornerShape(50)),
                colors = ButtonDefaults.buttonColors(Color(0xfffa4d56)),
            ){
                Icon(Icons.Filled.Dangerous, contentDescription = "eStop", tint= Color.White, modifier = Modifier.size(25.dp).scale(1.5f))
            }
        }
    }
}

/*
    RepeatPressButton: A function used to make the teleop movements (up, down, right, left, rrotate, and lrotate)
    continuous
 */
@Composable
fun RepeatPressButton(
    modifier: Modifier = Modifier,
    intervalMs: Long = 100L,
    onCommand: suspend () -> Unit,
    content: @Composable () -> Unit
) {
    val scope = rememberCoroutineScope()
    var job by remember { mutableStateOf<Job?>(null) }

    Box(
        modifier = modifier.pointerInput(Unit) {
            forEachGesture {
                awaitPointerEventScope {
                    awaitFirstDown(requireUnconsumed = false)
                    job = scope.launch {
                        onCommand()
                        while (isActive) {
                            delay(intervalMs)
                            onCommand()
                        }
                    }
                    do {
                        val event = awaitPointerEvent()
                        event.changes.forEach { it.consume() }
                    } while (event.changes.any { it.pressed })
                    job?.cancel()
                }
            }
        }
    ) {
        content()
    }
}

/*
    TeleopScreen: provides different directions the user can make the robot move
 */
@Composable
fun TeleopScreen(navController: NavHostController, viewModel:MyViewModel = viewModel()) {
    var isEStop = viewModel.isEStop

    Column(
        modifier = Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.spacedBy(1.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Spacer(modifier = Modifier.height(20.dp))


        Text(
            "Teleop Mode",
            style = TextStyle(fontSize = 3.2.em),
            modifier = Modifier.padding(bottom = 5.dp)
        )

        // Button: Up button to move the robot in an upwards direction
        RepeatPressButton(
            modifier = Modifier
                .size(90.dp, 24.dp)
                .clip(RoundedCornerShape(12.dp))
                .border(2.dp, Color(0xffc9f6f6), shape = RoundedCornerShape(12.dp))
                .background(Color(0xff005d5d), shape = RoundedCornerShape(12.dp)),
            intervalMs = 80L,
            onCommand = { sendCommand("up", "TeleopScreen") }
        ) {
            Box(modifier = Modifier.fillMaxSize()) {
                Icon(
                    imageVector = Icons.Filled.ArrowUpward,
                    contentDescription = "up",
                    tint = Color(0xffc9f6f6),
                    modifier = Modifier
                        .align(Alignment.CenterStart)
                        .padding(start = 4.dp)
                        .size(20.dp)
                )
                Text(
                    text = "Up",
                    color = Color.White,
                    modifier = Modifier.align(Alignment.Center)
                )
            }
        }

        Spacer(modifier = Modifier.height(10.dp))

        // Button: Let button to move the robot towards the left  direction
        Row(modifier = Modifier.wrapContentSize(Alignment.Center)) {
            RepeatPressButton(
                modifier = Modifier
                    .size(90.dp, 24.dp)
                    .clip(RoundedCornerShape(12.dp))
                    .border(2.dp, Color(0xffc9f6f6), shape = RoundedCornerShape(12.dp))
                    .background(Color(0xff005d5d), shape = RoundedCornerShape(12.dp)),
                intervalMs = 80L,
                onCommand = { sendCommand("left", "TeleopScreen") }
            ) {
                Box(modifier = Modifier.fillMaxSize()) {
                    Icon(
                        imageVector = Icons.Filled.ArrowBack,
                        contentDescription = "left",
                        tint = Color(0xffc9f6f6),
                        modifier = Modifier
                            .align(Alignment.CenterStart)
                            .padding(start = 4.dp)
                            .size(20.dp)
                    )
                    Text(
                        text = "Left",
                        color = Color.White,
                        modifier = Modifier.align(Alignment.Center)
                    )
                }
            }

            Spacer(modifier = Modifier.width(20.dp))

            // Button: Right button to move the robot towards the right direction
            RepeatPressButton(
                modifier = Modifier
                    .size(90.dp, 24.dp)
                    .clip(RoundedCornerShape(12.dp))
                    .border(2.dp, Color(0xffc9f6f6), shape = RoundedCornerShape(12.dp))
                    .background(Color(0xff005d5d), shape = RoundedCornerShape(12.dp)),
                intervalMs = 80L,
                onCommand = { sendCommand("right", "TeleopScreen") }
            ) {
                Box(modifier = Modifier.fillMaxSize()) {
                    Icon(
                        imageVector = Icons.Filled.ArrowForward,
                        contentDescription = "right",
                        tint = Color(0xffc9f6f6),
                        modifier = Modifier
                            .align(Alignment.CenterStart)
                            .padding(start = 4.dp)
                            .size(20.dp)
                    )
                    Text(
                        text = "Right",
                        color = Color.White,
                        modifier = Modifier.align(Alignment.Center)
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(7.dp))

        // Button: Down button to move the robot in a downwards direction
        RepeatPressButton(
            modifier = Modifier
                .size(90.dp, 24.dp)
                .clip(RoundedCornerShape(12.dp))
                .border(2.dp, Color(0xffc9f6f6), shape = RoundedCornerShape(12.dp))
                .background(Color(0xff005d5d), shape = RoundedCornerShape(12.dp)),
            intervalMs = 80L,
            onCommand = { sendCommand("down", "TeleopScreen") }
        ) {
            Box(modifier = Modifier.fillMaxSize()) {
                Icon(
                    imageVector = Icons.Filled.ArrowDownward,
                    contentDescription = "down",
                    tint = Color(0xffc9f6f6),
                    modifier = Modifier
                        .align(Alignment.CenterStart)
                        .padding(start = 4.dp)
                        .size(20.dp)
                )
                Text(
                    text = "Down",
                    color = Color.White,
                    modifier = Modifier.align(Alignment.Center)
                )
            }
        }

    Spacer(modifier = Modifier.height(10.dp))

    Row(
        modifier = Modifier.padding(1.dp),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically
    ) {
        // Button: Left rotate button to move the robot in a left rotation
        RepeatPressButton( // future work --> when a button follower is selected change the color to a different color e.g. green
            modifier = Modifier.
                size(85.dp, 20.dp)
                .border(2.dp, Color(0xffc9f6f6), shape = RoundedCornerShape(0.dp))
                .background(Color(0xff005d5d), shape = RoundedCornerShape(0.dp)),
            intervalMs = 80L,
            onCommand = { sendCommand("lrotate", "TeleopScreen") }
        ) {
            Box(modifier = Modifier.fillMaxSize()) {
                Icon(
                    imageVector = Icons.Filled.RotateLeft,
                    contentDescription = "lrotate",
                    tint = Color.White,
                    modifier = Modifier
                        .align(Alignment.CenterStart)
                        .padding(start = 4.dp)
                        .size(10.dp)
                        .scale(1f)
                )
                Text(
                    text = "LRotate",
                    color = Color.White,
                    modifier = Modifier.align(Alignment.Center)
                )
            }
        }

        Spacer(modifier = Modifier.width(5.dp))

        // Button: Right rotate button to move the robot in a right rotation
        RepeatPressButton(
            modifier = Modifier
                .size(85.dp, 20.dp)
                .border(2.dp, Color(0xffc9f6f6), shape = RoundedCornerShape(0.dp))
                .background(Color(0xff005d5d), shape = RoundedCornerShape(0.dp)),
            intervalMs = 80L,
            onCommand = { sendCommand("rrotate", "TeleopScreen") }
        ) {
            Box(modifier = Modifier.fillMaxSize()) {
                Icon(
                    imageVector = Icons.Filled.RotateLeft,
                    contentDescription = "rrotate",
                    tint = Color.White,
                    modifier = Modifier
                        .align(Alignment.CenterStart)
                        .padding(start = 4.dp)
                        .size(10.dp)
                        .scale(1f)
                )
                Text(
                    text = "RRotate",
                    color = Color.White,
                    modifier = Modifier.align(Alignment.Center)
                )
            }
        }
    }

        Spacer(modifier = Modifier.height(4.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.Center
        ) {

            Spacer(modifier = Modifier.height(40.dp))
            // Button: Back button to go back to the previous page & turn-off connection
            Button(
                onClick  = { navController.popBackStack()},
                shape    = RoundedCornerShape(50),
                modifier = Modifier.size(32.dp, 32.dp)
                    .shadow(elevation = 12.dp,
                        shape = RoundedCornerShape(50)),
                colors = ButtonDefaults.buttonColors(Color(0xff525252)),
            ){
                Icon(Icons.Filled.ArrowCircleLeft, contentDescription = "back", tint= Color.White, modifier = Modifier.size(22.dp).scale(1.5f))
            }

            Spacer(modifier = Modifier.width(30.dp))

            // Button: Freeze button to pause the robot in any state of action
            Button(
                onClick  = {
                    val action = "freeze"
                    sendCommand(action, "TeleopScreen")
                    viewModel.isEStop = !isEStop
                    navController.navigate("eStop")},
                shape    = RoundedCornerShape(50),
                modifier = Modifier.size(32.dp, 32.dp)
                    .shadow(elevation = 12.dp,
                        shape = RoundedCornerShape(50)),
                colors = ButtonDefaults.buttonColors(Color(0xfffa4d56)),
            ){
                Icon(Icons.Filled.Dangerous, contentDescription = "eStop", tint= Color.White, modifier = Modifier.size(22.dp).scale(1.5f))
            }
        }
    }
}

/*
    FollowerScreen: A function that allows a user to select a specific follower mode for the robot
 */
@Composable
fun FollowerScreen(navController: NavHostController, viewModel:MyViewModel = viewModel()) {
    // track whether QC follower is active
    var isQcFollowing by remember { mutableStateOf(false) }
    var isEStop = viewModel.isEStop

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(5.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(6.dp)
    ) {
        Spacer(modifier = Modifier.height(12.dp))
        Text("Follower Modes", style = TextStyle(fontSize = 3.em))

        // Button: QR Follower button to allow the robot to follow via a viewable QR code
        Button(
            onClick = {
                if (isQcFollowing) {
                    sendCommand("qrunfollow", "FollowerScreen")
                } else {
                    sendCommand("qrfollow", "FollowerScreen")
                }
                isQcFollowing = !isQcFollowing
            },
            modifier = Modifier.size(182.dp, 26.dp),
            colors = if (!isQcFollowing) ButtonDefaults.buttonColors(Color(0xff005d5d)) else ButtonDefaults.buttonColors(Color(0xffffbad3)),
            border = if (!isQcFollowing) ButtonDefaults.buttonBorder(borderStroke = BorderStroke(2.dp, Color(0xffc9f6f6))) else ButtonDefaults.buttonBorder(borderStroke = BorderStroke(2.dp, Color(0xffdc267f)))
        ) {
            Text(text = if (isQcFollowing) "QR Unfollow" else "QR Follower",
                color = if (!isQcFollowing) Color.White else Color.Black)
            Row(modifier = Modifier.fillMaxWidth().padding(2.dp),
                horizontalArrangement = Arrangement.Start,
                verticalAlignment = Alignment.CenterVertically) {
                if (!isQcFollowing)  Icon(Icons.Filled.QrCode, tint = Color(0xffc9f6f6), contentDescription = "camera",  modifier = Modifier.size(25.dp).scale(1f)) else Icon(Icons.Filled.QrCode, tint = Color(0xffdc267f), contentDescription = "camera",  modifier = Modifier.size(25.dp).scale(1f))

            }
        }

        // Button: CV Follower button to allow the robot to follow via computer vision
        Button(
            onClick = {
                navController.navigate("cvFollower")}, modifier = Modifier.size(182.dp, 26.dp),
            colors = if (viewModel.isCVFollower) ButtonDefaults.buttonColors(Color(0xff005d5d)) else ButtonDefaults.buttonColors(Color(0xffffbad3)),
            border = if (viewModel.isCVFollower) ButtonDefaults.buttonBorder(borderStroke = BorderStroke(2.dp, Color(0xffc9f6f6))) else ButtonDefaults.buttonBorder(borderStroke = BorderStroke(2.dp, Color(0xffdc267f)))
        ) {
            Text(text = if (viewModel.isCVFollower) "Camera Follower" else "Camera Unfollow",
                color = if (viewModel.isCVFollower) Color.White else Color.Black)
            Row(modifier = Modifier.fillMaxWidth().padding(2.dp),
                horizontalArrangement = Arrangement.Start,
                verticalAlignment = Alignment.CenterVertically) {
                if  (viewModel.isCVFollower)  Icon(Icons.Filled.CameraAlt, tint =  Color(0xffc9f6f6), contentDescription = "camera",  modifier = Modifier.size(25.dp).scale(1f)) else Icon(Icons.Filled.CameraAlt, tint =  Color(0xffc9f6f6), contentDescription = "camera",  modifier = Modifier.size(25.dp).scale(1f))
            }
        }

        // Button: BT Follower button to allow the robot to follow via bluetooth
        Button(
            onClick = {
                if (!viewModel.isBTFollower) {
                    sendCommand("btunfollow", "FollowerScreen")
                } else {
                    sendCommand("btfollow", "FollowerScreen")
                }
                viewModel.isBTFollower = !viewModel.isBTFollower}, modifier = Modifier.size(182.dp, 26.dp),
            colors = if (viewModel.isBTFollower) ButtonDefaults.buttonColors(Color(0xff005d5d)) else ButtonDefaults.buttonColors(Color(0xffffbad3)),
            border = if (viewModel.isBTFollower) ButtonDefaults.buttonBorder(borderStroke = BorderStroke(2.dp, Color(0xffc9f6f6))) else ButtonDefaults.buttonBorder(borderStroke = BorderStroke(2.dp, Color(0xffdc267f)))
        ) {
            Text(text = if (viewModel.isBTFollower) "Bluetooth Follower" else "Bluetooth Unfollow",
                color = if (viewModel.isBTFollower) Color.White else Color.Black)
            Row(modifier = Modifier.fillMaxWidth().padding(2.dp), // change to bluetooth text and icon
                horizontalArrangement = Arrangement.Start,
                verticalAlignment = Alignment.CenterVertically) {
                if  (viewModel.isBTFollower)  Icon(Icons.Filled.Bluetooth, tint =  Color(0xffc9f6f6), contentDescription = "camera",  modifier = Modifier.size(25.dp).scale(1f)) else Icon(Icons.Filled.Bluetooth, tint = Color(0xffdc267f), contentDescription = "camera",  modifier = Modifier.size(25.dp).scale(1f))
            }
        }

        // Button: FFollower button to allow the robot to follow via fusion
        Button(onClick = {
            if (!viewModel.isFFollower) {
                sendCommand("funfollow", "FollowerScreen")
            } else {
                sendCommand("ffollow", "FollowerScreen")
            }
            viewModel.isFFollower = !viewModel.isFFollower}, modifier = Modifier.size(182.dp, 26.dp),
            colors = if (viewModel.isFFollower) ButtonDefaults.buttonColors(Color(0xff005d5d)) else ButtonDefaults.buttonColors(Color(0xffffbad3)),
            border = if (viewModel.isFFollower) ButtonDefaults.buttonBorder(borderStroke = BorderStroke(2.dp, Color(0xffc9f6f6))) else ButtonDefaults.buttonBorder(borderStroke = BorderStroke(2.dp, Color(0xffdc267f)))
        ) {
            Text(text = if (viewModel.isFFollower) "Fusion Follower" else "Fusion Unfollow",
                color = if (viewModel.isFFollower) Color.White else Color.Black)
            Row(modifier = Modifier.fillMaxWidth().padding(2.dp),
                horizontalArrangement = Arrangement.Start,
                verticalAlignment = Alignment.CenterVertically) {
                if  (viewModel.isFFollower)  Icon(Icons.Filled.Merge, tint = Color(0xffc9f6f6), contentDescription = "camera",  modifier = Modifier.size(25.dp).scale(1f)) else Icon(Icons.Filled.Merge, tint = Color(0xffdc267f), contentDescription = "camera",  modifier = Modifier.size(25.dp).scale(1f))
            }
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.Center
        ) {

            Spacer(modifier = Modifier.height(55.dp))
            // Button: Back button to go back to the previous page & turn-off connection
            Button(
                onClick  = { navController.popBackStack()},
                shape    = RoundedCornerShape(50),
                modifier = Modifier.size(32.dp, 32.dp)
                    .shadow(elevation = 12.dp,
                        shape = RoundedCornerShape(50)),
                colors = ButtonDefaults.buttonColors(Color(0xff525252)),
            ){
                Icon(Icons.Filled.ArrowCircleLeft, contentDescription = "back", tint= Color.White, modifier = Modifier.size(22.dp).scale(1.5f))
            }

            Spacer(modifier = Modifier.width(24.dp))
            // Button: Freeze button to pause the robot in any state of action
            Button(
                onClick  = { val action = "freeze"
                    sendCommand(action, "FollowerScreen")
                    viewModel.isEStop = !isEStop
                    navController.navigate("eStop")

                    if (!viewModel.isFFollower) {
                        viewModel.isFFollower = !viewModel.isFFollower
                        sendCommand("funfollow", "FollowerScreen")
                    }

                    if (!viewModel.isBTFollower) {
                        viewModel.isBTFollower = !viewModel.isBTFollower
                        sendCommand("btunfollow", "FollowerScreen")
                    }
                    },
                shape    = RoundedCornerShape(50),
                modifier = Modifier.size(32.dp, 32.dp)
                    .shadow(elevation = 12.dp,
                        shape = RoundedCornerShape(50)),
                colors = ButtonDefaults.buttonColors(Color(0xfffa4d56)),
            ){
                Icon(Icons.Filled.Dangerous, contentDescription = "eStop", tint= Color.White, modifier = Modifier.size(22.dp).scale(1.5f))
            }
        }
    }
}

/*
    StopScreen: A function that is displayed when the robot is set to freeze by the user in emergency situations.
 */
@Composable
fun StopScreen(navController: NavHostController) {
    Column( modifier = Modifier
        .fillMaxSize()
        .verticalScroll(rememberScrollState())
        .padding(4.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(8.dp)){
        Spacer(modifier = Modifier.height(80.dp))
        Text("Emergency Stop!", style = TextStyle(fontSize = 3.em))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.Center
            ) {

                Spacer(modifier = Modifier.height(40.dp))
                Button(
                    onClick = {
                        var action = "unfreeze"
                        sendCommand(action, "FollowerScreen")
                        navController.popBackStack()},
                    shape = RoundedCornerShape(50),
                    modifier = Modifier.size(150.dp, 32.dp)
                        .shadow(
                            elevation = 12.dp,
                            shape = RoundedCornerShape(50)
                        ),
                    colors = ButtonDefaults.buttonColors(Color(0xfffa4d56))
                ) {
                    Text(text = "Release Freeze")
                }
            }
        }
}

/*
    ComputerVisionFollower: A function that allows the acquisition process to enable computer vision follower
    methodologies to occur when the user selects the button.
 */
@Composable
fun ComputerVisionFollower(navController: NavHostController, viewModel: MyViewModel) {
    Column( modifier = Modifier
        .fillMaxSize()
        .verticalScroll(rememberScrollState())
        .padding(4.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(8.dp)){

        Spacer(modifier = Modifier.height(20.dp))

        Text("Computer Vision Follower", style = TextStyle(fontSize = 2.em))
        Text("Select acquisition and cv follower to begin.", style = TextStyle(fontSize = 1.5.em))
        Spacer(modifier = Modifier.height(1.dp))

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.Center
        ) {
            // Button: CV Acquire button allows the computer vision to do acquisition mode and gain enough samples to track/follow the user
            Button(
                onClick = {
                    sendCommand(action="cvacquire", page="cvTimer")
                    navController.navigate("cvTimer")
                },
                shape = RoundedCornerShape(50),
                modifier = Modifier.size(200.dp, 38.dp)
                    .shadow(
                        elevation = 12.dp,
                        shape = RoundedCornerShape(50)
                    ),
                colors = ButtonDefaults.buttonColors(Color(0xff005d5d)),
                border = ButtonDefaults.buttonBorder(borderStroke = BorderStroke(2.dp, Color(0xffc9f6f6)))
            ) {
                Text(text = "Acquisition")
            }
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.Center
        ) {
            Spacer(modifier = Modifier.height(10.dp))
            // Button: CV Follower button allows the computer vision follower to be created by the user
            Button(
                onClick = {
                    if (!viewModel.isCVFollower) {
                        sendCommand("cvunfollow", "FollowerScreen")
                    } else {
                        sendCommand("cvfollow", "FollowerScreen")

                    }
                    viewModel.isCVFollower = !viewModel.isCVFollower
                },
                shape = RoundedCornerShape(50),
                modifier = Modifier.size(200.dp, 38.dp)
                    .shadow(
                        elevation = 12.dp,
                        shape = RoundedCornerShape(50)
                    ),
                colors = if (viewModel.isCVFollower) ButtonDefaults.buttonColors(Color(0xff005d5d)) else ButtonDefaults.buttonColors(Color(0xffffbad3)),
                border = if (viewModel.isCVFollower) ButtonDefaults.buttonBorder(borderStroke = BorderStroke(2.dp, Color(0xffc9f6f6))) else  ButtonDefaults.buttonBorder(borderStroke = BorderStroke(2.dp, Color(0xffdc267f)))
            ) {
                Text(text = if (viewModel.isCVFollower) "CV Follower" else "CV Unfollow",
                    color = if (viewModel.isCVFollower) Color.White else Color.Black)
            }
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.Center
        ) {

            Spacer(modifier = Modifier.height(40.dp))

            // Button: Back button is to provide the ability to move back and go to the commands page
            Button(
            onClick  = { navController.popBackStack()},
            shape    = RoundedCornerShape(50),
            modifier = Modifier.size(42.dp, 42.dp)
                .shadow(elevation = 12.dp,
                    shape = RoundedCornerShape(50)),
            colors = ButtonDefaults.buttonColors(Color(0xff525252)),
            ){
                Icon(Icons.Filled.ArrowCircleLeft, contentDescription = "back", tint= Color.White, modifier = Modifier.size(22.dp).scale(2f))
            }

            Spacer(modifier = Modifier.width(24.dp))

            // Button: Freeze button allows the user to freeze the current state of the robot in emergency situations
            Button(
                onClick  = { val action = "freeze"
                    sendCommand(action, "FollowerScreen")
                    viewModel.isEStop = !viewModel.isEStop
                    navController.navigate("eStop")
                    sendCommand("cvunfollow", "FollowerScreen")
                    viewModel.isCVFollower = !viewModel.isCVFollower },
                shape    = RoundedCornerShape(50),
                modifier = Modifier.size(42.dp, 42.dp)
                    .shadow(elevation = 12.dp,
                        shape = RoundedCornerShape(50)),
                colors = ButtonDefaults.buttonColors(Color(0xfffa4d56)),
            ){
                Icon(Icons.Filled.Dangerous, contentDescription = "eStop", tint= Color.White, modifier = Modifier.size(22.dp).scale(2f))
            }
        }
    }
}

/*
    ComputerVisionTimer: A function that sets a 10 second timer to allow acquistion to occur for the computer
    vision follower functionality.
 */
@Composable
fun ComputerVisionTimer(navController: NavController) {
    var timeLeft by remember { mutableStateOf(10) }

    LaunchedEffect(Unit) {
        while (timeLeft > 0) {
            delay(1000L) // creates a full second wait
            timeLeft--
        }
        navController.popBackStack()
    }

    Column( modifier = Modifier
        .fillMaxSize()
        .padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center){
        Text("Stand back to start acquisition.", style = TextStyle(fontSize = 1.5.em))
        Spacer(modifier = Modifier.height(5.dp))
        Text("Move & Walk Around!", style = TextStyle(fontSize = 2.em))
        Spacer(modifier = Modifier.height(20.dp))
        Text(text = "Total Remaining Time : $timeLeft")
    }
}

@Preview(device = WearDevices.SMALL_ROUND, showSystemUi = true)
@Composable
fun DefaultPreview() {
    WearApp()
}

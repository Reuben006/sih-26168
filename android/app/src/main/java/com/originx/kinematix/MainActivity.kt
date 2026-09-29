package com.originx.kinematix

import android.Manifest
import android.annotation.SuppressLint
import android.content.Intent
import android.content.pm.PackageManager
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.net.Uri
import android.os.Build
import android.graphics.Color
import android.view.RoundedCorner
import android.view.WindowManager
import android.widget.FrameLayout
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.webkit.*
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import kotlin.math.ceil
import kotlin.math.max
import androidx.webkit.WebViewAssetLoader
import org.json.JSONArray
import org.json.JSONObject

/** Local asset UI and foreground-only sensor capture. No location is uploaded. */
class MainActivity : AppCompatActivity(), SensorEventListener, LocationListener {
    private lateinit var webView: WebView
    private lateinit var safeContainer: FrameLayout
    @Volatile private var fullscreenEnabled = true
    private lateinit var sensors: SensorManager
    private lateinit var locations: LocationManager
    private val handler = Handler(Looper.getMainLooper())
    private var reportText = ""
    private val reportSaver = registerForActivityResult(ActivityResultContracts.CreateDocument("application/json")) { uri ->
        if (uri != null) contentResolver.openOutputStream(uri)?.use { it.write(reportText.toByteArray(Charsets.UTF_8)) }
        reportText = ""
    }
    private var gnssMessage = "Searching for GPS position. Try outdoors with a clear sky view."
    private var statusTicks = 0
    private var active = false
    private var wanted = false
    private var acc = floatArrayOf(0f,0f,9.80665f)
    private var gyro = floatArrayOf(0f,0f,0f)
    private var gravity = floatArrayOf(0f,0f,9.80665f)
    private var gravitySensor = false
    private var uploadCallback: ValueCallback<Array<Uri>>? = null
    private val permission = registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { result ->
        if (result[Manifest.permission.ACCESS_FINE_LOCATION] == true && wanted) beginCapture()
        else emit(JSONObject().put("type","error").put("message","Precise location permission is required to initialize navigation."))
    }
    private val picker = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        uploadCallback?.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(result.resultCode,result.data))
        uploadCallback = null
    }
    private val tick = object : Runnable {
        override fun run() {
            if (!active) return
            emit(JSONObject().put("type","imu").put("time",SystemClock.elapsedRealtime())
                .put("acc",JSONArray(acc.toList())).put("gyro",JSONArray(gyro.toList())).put("gravity",JSONArray(gravity.toList())))
            if (statusTicks++ % 10 == 0) emit(JSONObject().put("type","gnss-status").put("message",
                if (!locations.isProviderEnabled(LocationManager.GPS_PROVIDER)) "Phone Location is off. Enable Location in Quick Settings." else gnssMessage))
            handler.postDelayed(this,100)
        }
    }
    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        fullscreenEnabled = state?.getBoolean("fullscreen", true) ?: true
        WindowCompat.setDecorFitsSystemWindows(window, false)
        window.statusBarColor = Color.TRANSPARENT
        window.navigationBarColor = Color.TRANSPARENT
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            window.attributes = window.attributes.apply {
                layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES
            }
        }
        sensors = getSystemService(SENSOR_SERVICE) as SensorManager
        locations = getSystemService(LOCATION_SERVICE) as LocationManager
        val loader = WebViewAssetLoader.Builder().addPathHandler("/assets/",WebViewAssetLoader.AssetsPathHandler(this)).build()
        webView = WebView(this)
        webView.settings.javaScriptEnabled = true
        webView.settings.mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
        webView.settings.domStorageEnabled = true
        webView.settings.allowFileAccess = false
        webView.settings.allowContentAccess = true
        webView.webViewClient = object : WebViewClient() {
            override fun shouldInterceptRequest(view: WebView,request: WebResourceRequest): WebResourceResponse? = loader.shouldInterceptRequest(request.url)
            override fun shouldOverrideUrlLoading(view: WebView,request: WebResourceRequest): Boolean {
                if (request.url.host == "appassets.androidplatform.net") return false
                if (request.url.scheme in listOf("https","http")) startActivity(Intent(Intent.ACTION_VIEW,request.url))
                return true
            }
        }
        webView.webChromeClient = object : WebChromeClient() {
            override fun onShowFileChooser(view: WebView?,callback: ValueCallback<Array<Uri>>?,params: FileChooserParams?): Boolean {
                uploadCallback?.onReceiveValue(null); uploadCallback = callback
                picker.launch(Intent(Intent.ACTION_GET_CONTENT).apply { addCategory(Intent.CATEGORY_OPENABLE);type="*/*" })
                return true
            }
        }
        webView.addJavascriptInterface(object {
            @JavascriptInterface fun isFullscreen(): Boolean = fullscreenEnabled
            @JavascriptInterface fun setFullscreen(enabled: Boolean) { runOnUiThread { fullscreenEnabled=enabled;applyFullscreen() } }
            @JavascriptInterface fun saveReport(name: String, text: String) { runOnUiThread { reportText=text;reportSaver.launch(name.take(100)) } }
            @JavascriptInterface fun startSensors() { runOnUiThread {
                wanted = true
                if(ContextCompat.checkSelfPermission(this@MainActivity,Manifest.permission.ACCESS_FINE_LOCATION)==PackageManager.PERMISSION_GRANTED) beginCapture()
                else permission.launch(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION,Manifest.permission.ACCESS_COARSE_LOCATION))
            } }
            @JavascriptInterface fun stopSensors() { runOnUiThread { wanted=false;stopCapture() } }
        },"KinematiX")
        safeContainer = FrameLayout(this).apply {
            setBackgroundColor(Color.rgb(17, 18, 20))
            addView(webView, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT))
        }
        // Pad the native viewport itself. The WebView never lays text under a notch.
        ViewCompat.setOnApplyWindowInsetsListener(safeContainer) { view, insets ->
            val safe = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout())
            val gestures = insets.getInsets(WindowInsetsCompat.Type.systemGestures())
            val keyboard = insets.getInsets(WindowInsetsCompat.Type.ime())
            var corner = (8 * resources.displayMetrics.density).toInt()
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val nativeInsets = insets.toWindowInsets()
                for (position in listOf(RoundedCorner.POSITION_TOP_LEFT, RoundedCorner.POSITION_TOP_RIGHT,
                    RoundedCorner.POSITION_BOTTOM_LEFT, RoundedCorner.POSITION_BOTTOM_RIGHT)) {
                    val radius = nativeInsets?.getRoundedCorner(position)?.radius ?: 0
                    // Quarter-circle safe diagonal plus the CSS content margin.
                    corner = max(corner, ceil(radius * (1.0 - 1.0 / kotlin.math.sqrt(2.0))).toInt())
                }
            }
            view.setPadding(max(corner, max(safe.left, gestures.left)), max(corner, safe.top),
                max(corner, max(safe.right, gestures.right)), max(corner, max(keyboard.bottom, max(safe.bottom, gestures.bottom))))
            WindowInsetsCompat.CONSUMED
        }
        setContentView(safeContainer)
        ViewCompat.requestApplyInsets(safeContainer)
        applyFullscreen()
        webView.loadUrl("https://appassets.androidplatform.net/assets/index.html")
    }
    private fun applyFullscreen() {
        val controller = WindowCompat.getInsetsController(window, window.decorView)
        controller.systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        if (fullscreenEnabled) controller.hide(WindowInsetsCompat.Type.systemBars())
        else controller.show(WindowInsetsCompat.Type.systemBars())
        if (::safeContainer.isInitialized) ViewCompat.requestApplyInsets(safeContainer)
    }
    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) applyFullscreen()
    }
    override fun onSaveInstanceState(outState: Bundle) {
        outState.putBoolean("fullscreen", fullscreenEnabled)
        super.onSaveInstanceState(outState)
    }
    @SuppressLint("MissingPermission")
    private fun beginCapture() {
        if(active) return
        if(sensors.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)==null || sensors.getDefaultSensor(Sensor.TYPE_GYROSCOPE)==null){
            emit(JSONObject().put("type","error").put("message","This phone needs both an accelerometer and gyroscope."));return
        }
        gnssMessage="Searching for GPS position. Try outdoors with a clear sky view."
        statusTicks=0
        active=true
        gravitySensor=sensors.getDefaultSensor(Sensor.TYPE_GRAVITY)!=null
        for(type in listOf(Sensor.TYPE_ACCELEROMETER,Sensor.TYPE_GYROSCOPE,Sensor.TYPE_GRAVITY)) {
            sensors.getDefaultSensor(type)?.let { sensors.registerListener(this,it,20000) }
        }
        try { locations.requestLocationUpdates(LocationManager.GPS_PROVIDER,1000L,0f,this) }
        catch(e:SecurityException){ stopCapture();return }
        handler.post(tick)
    }
    private fun stopCapture(){ active=false;handler.removeCallbacks(tick);sensors.unregisterListener(this);locations.removeUpdates(this) }
    private fun emit(data:JSONObject){webView.evaluateJavascript("window.dispatchEvent(new CustomEvent('kinematix-sensor',{detail:$data}));",null)}
    override fun onSensorChanged(event:SensorEvent){
        when(event.sensor.type){
            Sensor.TYPE_ACCELEROMETER -> { acc=event.values.clone();if(!gravitySensor)for(i in 0..2)gravity[i]=.98f*gravity[i]+.02f*acc[i] }
            Sensor.TYPE_GYROSCOPE -> gyro=event.values.clone()
            Sensor.TYPE_GRAVITY -> gravity=event.values.clone()
        }
    }
    override fun onLocationChanged(location:Location){
        if (!location.hasAccuracy() || location.accuracy > 30) {
            gnssMessage="GPS received, but position accuracy is insufficient (need 30 m or better)."; return
        }
        if (!location.hasSpeed() || !location.hasBearing()) {
            gnssMessage="GPS position acquired. Waiting for speed and travel direction; move outdoors to initialize navigation."; return
        }
        gnssMessage="GPS position, speed and heading received."
        emit(JSONObject().put("type","gnss").put("time",SystemClock.elapsedRealtime())
            .put("lat",location.latitude).put("lon",location.longitude).put("speed",location.speed).put("bearing",location.bearing).put("accuracy",location.accuracy))
    }
    override fun onProviderEnabled(provider:String) { if (provider == LocationManager.GPS_PROVIDER) gnssMessage="Location enabled. Searching for a fresh GPS fix." }
    override fun onProviderDisabled(provider:String) { if (provider == LocationManager.GPS_PROVIDER) gnssMessage="Phone Location is off. Enable Location in Quick Settings." }
    override fun onAccuracyChanged(sensor:Sensor?,accuracy:Int){}
    override fun onPause(){stopCapture();super.onPause()}
    override fun onResume(){super.onResume();if(wanted&&ContextCompat.checkSelfPermission(this,Manifest.permission.ACCESS_FINE_LOCATION)==PackageManager.PERMISSION_GRANTED)beginCapture()}
    override fun onDestroy(){stopCapture();uploadCallback?.onReceiveValue(null);webView.removeJavascriptInterface("KinematiX");webView.destroy();super.onDestroy()}
}

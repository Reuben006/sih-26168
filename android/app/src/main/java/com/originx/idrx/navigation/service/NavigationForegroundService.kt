package com.originx.idrx.navigation.service

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat

class NavigationForegroundService : Service(), SensorEventListener, LocationListener {
    private lateinit var sensorManager: SensorManager
    private lateinit var locationManager: LocationManager

    private var isGnssAvailable = true
    private var lastGnssTime = 0L
    private val OUTAGE_TIMEOUT_MS = 3000L
    private var posX = 0.0
    private var posY = 0.0
    private var forwardVelocity = 0.0
    private var lastImuTimestamp = 0L

    override fun onCreate() {
        super.onCreate()
        startNotification()

        sensorManager = getSystemService(Context.SENSOR_SERVICE) as SensorManager
        locationManager = getSystemService(Context.LOCATION_SERVICE) as LocationManager

        val accel = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
        val gyro = sensorManager.getDefaultSensor(Sensor.TYPE_GYROSCOPE)

        sensorManager.registerListener(this, accel, SensorManager.SENSOR_DELAY_FASTEST)
        sensorManager.registerListener(this, gyro, SensorManager.SENSOR_DELAY_FASTEST)

        try {
            locationManager.requestLocationUpdates(LocationManager.GPS_PROVIDER, 1000L, 0f, this)
        } catch (e: SecurityException) {
            e.printStackTrace()
        }
    }

    private fun startNotification() {
        val channelId = "idrx_channel"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                channelId,
                "IDR-X Dead Reckoning",
                NotificationManager.IMPORTANCE_LOW
            )
            val manager = getSystemService(NotificationManager::class.java)
            manager?.createNotificationChannel(channel)
        }

        val notification = NotificationCompat.Builder(this, channelId)
            .setContentTitle("IDR-X Active")
            .setContentText("Dead reckoning navigation engine running")
            .setSmallIcon(android.R.drawable.ic_menu_compass)
            .setOngoing(true)
            .build()

        startForeground(101, notification)
    }

    override fun onSensorChanged(event: SensorEvent) {
        val now = System.currentTimeMillis()
        if (now - lastGnssTime > OUTAGE_TIMEOUT_MS && isGnssAvailable) {
            isGnssAvailable = false
        }
        if (event.sensor.type == Sensor.TYPE_ACCELEROMETER) {
            if (lastImuTimestamp != 0L) {
                val dt = (event.timestamp - lastImuTimestamp) * 1e-9
                if (!isGnssAvailable) {
                    val ax = event.values[0]
                    forwardVelocity += ax * dt
                    posX += forwardVelocity * dt
                }
            }
            lastImuTimestamp = event.timestamp
        }
    }

    override fun onLocationChanged(location: Location) {
        lastGnssTime = System.currentTimeMillis()
        isGnssAvailable = true
        posX = location.latitude
        posY = location.longitude
        forwardVelocity = location.speed.toDouble()
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}
    override fun onBind(intent: Intent?): IBinder? = null
}
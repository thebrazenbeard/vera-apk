plugins {
    id("com.android.application")
}

android {
    namespace = "com.vera.companion"
    compileSdk = 37

    defaultConfig {
        applicationId = "com.vera.companion"
        minSdk = 29
        targetSdk = 37
        versionCode = 1
        versionName = "0.1.0"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    testImplementation("junit:junit:4.13.2")
}

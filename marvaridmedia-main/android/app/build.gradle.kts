plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// Ilova ochadigan sayt manzili (Railway domeni)
val siteUrl: String = (project.findProperty("SITE_URL") as String?)
    ?: "https://marvaridmedia-production.up.railway.app/"

// Imzo kaliti GitHub Secrets orqali beriladi (KEYSTORE_BASE64, KEYSTORE_PASSWORD, KEY_ALIAS, KEY_PASSWORD)
val keystoreFile = rootProject.file("release.jks")
val hasReleaseKey = keystoreFile.exists() && System.getenv("KEYSTORE_PASSWORD") != null

android {
    namespace = "uz.marvaridmedia.app"
    compileSdk = 36

    defaultConfig {
        applicationId = "uz.marvaridmedia.app"
        minSdk = 23
        targetSdk = 36
        versionCode = (System.getenv("VERSION_CODE") ?: "1").toInt()
        versionName = System.getenv("VERSION_NAME") ?: "1.0"
        buildConfigField("String", "SITE_URL", "\"$siteUrl\"")
    }

    signingConfigs {
        if (hasReleaseKey) {
            create("release") {
                storeFile = keystoreFile
                storePassword = System.getenv("KEYSTORE_PASSWORD")
                keyAlias = System.getenv("KEY_ALIAS")
                keyPassword = System.getenv("KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            if (hasReleaseKey) signingConfig = signingConfigs.getByName("release")
        }
    }

    buildFeatures { buildConfig = true }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.activity:activity-ktx:1.9.3")
    implementation("androidx.core:core-splashscreen:1.0.1")
}

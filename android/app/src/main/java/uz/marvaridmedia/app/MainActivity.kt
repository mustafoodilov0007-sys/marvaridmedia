package uz.marvaridmedia.app

import android.annotation.SuppressLint
import android.content.ActivityNotFoundException
import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.view.ViewGroup
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.Toast
import androidx.activity.addCallback
import androidx.appcompat.app.AppCompatActivity
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.core.view.ViewCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat

/** Marvarid Media — saytni (katalog, shorts, qidiruv) ochadigan ilova. Kino Telegram botda ochiladi. */
class MainActivity : AppCompatActivity() {

    private lateinit var root: FrameLayout
    private lateinit var web: WebView
    private var fullscreenView: View? = null
    private var fullscreenCallback: WebChromeClient.CustomViewCallback? = null
    private var pageReady = false

    private val siteUri: Uri by lazy { Uri.parse(BuildConfig.SITE_URL) }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        val splash = installSplashScreen()
        super.onCreate(savedInstanceState)
        splash.setKeepOnScreenCondition { !pageReady }

        WindowCompat.setDecorFitsSystemWindows(window, false)
        root = FrameLayout(this).apply { setBackgroundColor(DARK) }
        web = WebView(this)
        root.addView(web, FrameLayout.LayoutParams(MATCH, MATCH))
        setContentView(root)

        // Status bar va pastki panel ostiga kirib ketmasligi uchun
        ViewCompat.setOnApplyWindowInsetsListener(root) { v, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout())
            if (fullscreenView == null) v.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            insets
        }
        applyTheme("dark")

        web.setBackgroundColor(DARK)
        web.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            mediaPlaybackRequiresUserGesture = false
            cacheMode = WebSettings.LOAD_DEFAULT
            loadWithOverviewMode = true
            useWideViewPort = true
            userAgentString = "$userAgentString MarvaridApp/${BuildConfig.VERSION_NAME}"
        }
        web.addJavascriptInterface(Bridge(), "MarvaridApp")

        web.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                val uri = request.url
                if (uri.host == siteUri.host || uri.scheme == "file") return false
                openExternal(uri)
                return true
            }

            override fun onPageFinished(view: WebView, url: String?) {
                pageReady = true
            }

            override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                if (request.isForMainFrame) {
                    pageReady = true
                    view.loadUrl(OFFLINE_PAGE)
                }
            }
        }

        // Video to'liq ekranda
        web.webChromeClient = object : WebChromeClient() {
            override fun onShowCustomView(view: View, callback: CustomViewCallback) {
                if (fullscreenView != null) {
                    callback.onCustomViewHidden(); return
                }
                fullscreenView = view
                fullscreenCallback = callback
                root.setPadding(0, 0, 0, 0)
                root.addView(view, FrameLayout.LayoutParams(MATCH, MATCH))
                WindowInsetsControllerCompat(window, root).apply {
                    hide(WindowInsetsCompat.Type.systemBars())
                    systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
                }
            }

            override fun onHideCustomView() = exitFullscreen()
        }

        onBackPressedDispatcher.addCallback(this) { handleBack() }

        // Splash ekran uzoq qolib ketmasin
        root.postDelayed({ pageReady = true }, 4000)

        if (savedInstanceState != null) web.restoreState(savedInstanceState)
        else web.loadUrl(BuildConfig.SITE_URL)
    }

    private fun exitFullscreen() {
        val view = fullscreenView ?: return
        root.removeView(view)
        fullscreenView = null
        fullscreenCallback?.onCustomViewHidden()
        fullscreenCallback = null
        WindowInsetsControllerCompat(window, root).show(WindowInsetsCompat.Type.systemBars())
        ViewCompat.requestApplyInsets(root)
    }

    private fun handleBack() {
        if (fullscreenView != null) {
            exitFullscreen(); return
        }
        if (web.url?.startsWith("file:") == true) {
            finish(); return
        }
        web.evaluateJavascript("(window.mmBack && window.mmBack()) ? '1' : '0'") { result ->
            if (result?.contains("1") != true) finish()
        }
    }

    /** t.me havolalari Telegram ilovasida, qolganlari brauzerda ochiladi. */
    private fun openExternal(uri: Uri) {
        try {
            startActivity(Intent(Intent.ACTION_VIEW, uri).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        } catch (e: ActivityNotFoundException) {
            val msg = if (uri.host == "t.me") getString(R.string.no_telegram) else getString(R.string.no_app)
            Toast.makeText(this, msg, Toast.LENGTH_LONG).show()
        }
    }

    private fun applyTheme(theme: String) {
        val dark = theme != "light"
        val color = if (dark) DARK else LIGHT
        root.setBackgroundColor(color)
        if (::web.isInitialized) web.setBackgroundColor(color)
        WindowInsetsControllerCompat(window, root).apply {
            isAppearanceLightStatusBars = !dark
            isAppearanceLightNavigationBars = !dark
        }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        web.saveState(outState)
    }

    override fun onPause() {
        super.onPause()
        web.onPause()
    }

    override fun onResume() {
        super.onResume()
        web.onResume()
    }

    override fun onDestroy() {
        (web.parent as? ViewGroup)?.removeView(web)
        web.destroy()
        super.onDestroy()
    }

    /** Sayt bilan aloqa: window.MarvaridApp.* */
    inner class Bridge {
        @JavascriptInterface
        fun setTheme(theme: String) {
            runOnUiThread { applyTheme(theme) }
        }

        @JavascriptInterface
        fun reload() {
            runOnUiThread { web.loadUrl(BuildConfig.SITE_URL) }
        }
    }

    companion object {
        private const val MATCH = ViewGroup.LayoutParams.MATCH_PARENT
        private const val OFFLINE_PAGE = "file:///android_asset/offline.html"
        private val DARK = Color.parseColor("#0A0C13")
        private val LIGHT = Color.parseColor("#F5F6FB")
    }
}

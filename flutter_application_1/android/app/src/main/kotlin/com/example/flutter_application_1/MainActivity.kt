package com.example.flutter_application_1

import android.os.Bundle // ★ android.os.Bundle 로 수정
import android.webkit.WebView
import io.flutter.embedding.android.FlutterActivity

class MainActivity: FlutterActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // 안드로이드 웹뷰 디버깅을 강제로 활성화합니다.
        WebView.setWebContentsDebuggingEnabled(true)
    }
}
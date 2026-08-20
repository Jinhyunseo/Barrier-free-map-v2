import 'package:flutter/foundation.dart'; // kIsWeb 사용
import 'package:flutter/material.dart';
import 'package:kakao_map_plugin/kakao_map_plugin.dart' as kakao;

// 최신 웹(Wasm 대응) 표준 패키지
import 'dart:js_interop'; // 💡 String -> JSAny 변환(.toJS)에 필요
import 'dart:ui_web' as ui_web;
import 'package:web/web.dart' as web;

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  
  if (!kIsWeb) {
    // 모바일(Android/iOS) 환경일 때만 네이티브 키 초기화
    kakao.AuthRepository.initialize(appKey: '670b90c371e83c8aa86726e82acc3cf3');
  } else {
    // 웹 환경일 때 HTML IFrame 지도를 등록
    _registerWebMapIframe();
  }

  runApp(const MyApp());
}

// 웹(Chrome) 전용 카카오 지도 Iframe 등록 함수
// 웹(Chrome) 전용 카카오 지도 Iframe 등록 함수
void _registerWebMapIframe() {
  ui_web.platformViewRegistry.registerViewFactory('kakao-web-map-view', (int viewId) {
    final iframe = web.HTMLIFrameElement()
      ..srcdoc = '''
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <style>html, body, #map { width:100%; height:100%; margin:0; padding:0; }</style>
          <script type="text/javascript" src="//dapi.kakao.com/v2/maps/sdk.js?appkey=670b90c371e83c8aa86726e82acc3cf3"></script>
        </head>
        <body>
          <div id="map"></div>
          <script>
            var container = document.getElementById('map');
            var options = {
              center: new kakao.maps.LatLng(37.411337, 127.128696),
              level: 4
            };
            var map = new kakao.maps.Map(container, options);
          </script>
        </body>
        </html>
      '''.toJS // 💡 문자열 끝에 .toJS를 붙여주면 JSAny 타입 에러가 해결됩니다.
      ..style.border = 'none'
      ..style.width = '100%'
      ..style.height = '100%';
    return iframe;
  });
}
class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return const MaterialApp(
      debugShowCheckedModeBanner: false,
      home: RouteSearchScreen(),
    );
  }
}

class RouteSearchScreen extends StatefulWidget {
  const RouteSearchScreen({super.key});

  @override
  State<RouteSearchScreen> createState() => _RouteSearchScreenState();
}

class _RouteSearchScreenState extends State<RouteSearchScreen> {
  kakao.KakaoMapController? mapController;

  final TextEditingController _startController = TextEditingController(text: '야탑역');
  final TextEditingController _endController = TextEditingController(text: '판교역');

  String selectedUserType = '휠체어';
  final List<String> userTypes = ['휠체어', '노약자', '유모차'];

  final kakao.LatLng startLatLng = kakao.LatLng(37.411337, 127.128696);
  final kakao.LatLng endLatLng = kakao.LatLng(37.394776, 127.11116);

  List<kakao.Marker> markers = [];
  List<kakao.Polyline> polylines = [];
  List<String> recommendationReasons = [];

  @override
  void initState() {
    super.initState();
    markers = [
      kakao.Marker(markerId: 'start', latLng: startLatLng),
      kakao.Marker(markerId: 'end', latLng: endLatLng),
    ];
    _updateRoute(selectedUserType);
  }

  void _updateRoute(String type) {
    List<kakao.LatLng> detailedPath = [];
    List<String> reasons = [];

    if (type == '휠체어') {
      detailedPath = [
        kakao.LatLng(37.411337, 127.128696),
        kakao.LatLng(37.408000, 127.127000),
        kakao.LatLng(37.394776, 127.111160),
      ];
      reasons = [
        '경사도 5% 이하의 평지 위주 도로',
        '턱 없는 인도 및 엘리베이터 이동 동선 포함',
        '보도블록 파손 구간 우회 적용',
      ];
    } else if (type == '노약자') {
      detailedPath = [
        kakao.LatLng(37.411337, 127.128696),
        kakao.LatLng(37.405500, 127.126800),
        kakao.LatLng(37.394776, 127.111160),
      ];
      reasons = [
        '계단 대신 에스컬레이터 우선 동선 안내',
        '경사로 완만 구간 및 중간 쉼터 우회 도로',
      ];
    } else {
      detailedPath = [
        kakao.LatLng(37.411337, 127.128696),
        kakao.LatLng(37.401200, 127.125100),
        kakao.LatLng(37.394776, 127.111160),
      ];
      reasons = [
        '유모차 진입 가능한 넓은 보도 폭 위주',
        '지하보도 대신 지상 횡단보도 이용',
      ];
    }

    setState(() {
      selectedUserType = type;
      recommendationReasons = reasons;
      polylines = [
        kakao.Polyline(
          polylineId: 'route_line',
          points: detailedPath,
          strokeColor: Colors.blue,
          strokeWidth: 6,
          strokeOpacity: 0.8,
        ),
      ];
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        children: [
          // 1. 지도 영역: 웹 환경일 때와 모바일 환경일 때를 구분
          kIsWeb
              ? const HtmlElementView(viewType: 'kakao-web-map-view') // 웹 환경: HTML Iframe 지도
              : kakao.KakaoMap(                                       // 모바일 환경: 플러그인 지도
                  onMapCreated: (controller) async {
                    mapController = controller;
                    setState(() {});
                    if (markers.isNotEmpty) await mapController?.addMarker(markers: markers);
                    if (polylines.isNotEmpty) await mapController?.addPolyline(polylines: polylines);
                  },
                  center: startLatLng,
                  markers: markers,
                  polylines: polylines,
                ),

          // 2. 상단 패널
          Positioned(
            top: 50,
            left: 16,
            right: 16,
            child: Card(
              elevation: 6,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              child: Padding(
                padding: const EdgeInsets.all(14.0),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    TextField(
                      controller: _startController,
                      decoration: const InputDecoration(
                        prefixIcon: Icon(Icons.my_location, color: Colors.blue),
                        hintText: '출발지 입력',
                        isDense: true,
                        border: InputBorder.none,
                      ),
                    ),
                    const Divider(height: 1),
                    TextField(
                      controller: _endController,
                      decoration: const InputDecoration(
                        prefixIcon: Icon(Icons.location_on, color: Colors.red),
                        hintText: '목적지 입력',
                        isDense: true,
                        border: InputBorder.none,
                      ),
                    ),
                    const SizedBox(height: 10),
                    SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      child: Row(
                        children: userTypes.map((type) {
                          final isSelected = selectedUserType == type;
                          return Padding(
                            padding: const EdgeInsets.only(right: 6.0),
                            child: ChoiceChip(
                              label: Text(type),
                              selected: isSelected,
                              selectedColor: Colors.blue.shade100,
                              onSelected: (selected) {
                                if (selected) {
                                  _updateRoute(type);
                                }
                              },
                            ),
                          );
                        }).toList(),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),

          // 3. 하단 바텀시트
          DraggableScrollableSheet(
            initialChildSize: 0.28,
            minChildSize: 0.15,
            maxChildSize: 0.60,
            builder: (BuildContext context, ScrollController scrollController) {
              return Container(
                decoration: const BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
                  boxShadow: [BoxShadow(blurRadius: 10, color: Colors.black26)],
                ),
                child: ListView(
                  controller: scrollController,
                  padding: const EdgeInsets.all(20),
                  children: [
                    Center(
                      child: Container(
                        width: 40,
                        height: 5,
                        decoration: BoxDecoration(
                          color: Colors.grey[300],
                          borderRadius: BorderRadius.circular(10),
                        ),
                      ),
                    ),
                    const SizedBox(height: 15),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          '$selectedUserType 맞춤 추천 경로',
                          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                        ),
                        const Text(
                          '약 22분 (1.8km)',
                          style: TextStyle(fontSize: 16, color: Colors.blue, fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                    const SizedBox(height: 15),
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.grey[100],
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            '💡 이 경로를 추천하는 이유',
                            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14),
                          ),
                          const SizedBox(height: 8),
                          ...recommendationReasons.map((reason) => _buildReasonItem(reason)).toList(),
                        ],
                      ),
                    ),
                    const SizedBox(height: 15),
                    ElevatedButton(
                      onPressed: () {},
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.blueAccent,
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                      child: const Text('경로 안내 시작', style: TextStyle(fontSize: 16, color: Colors.white)),
                    ),
                  ],
                ),
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _buildReasonItem(String text) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2.0),
      child: Row(
        children: [
          const Icon(Icons.check_circle_outline, size: 16, color: Colors.green),
          const SizedBox(width: 8),
          Expanded(child: Text(text, style: const TextStyle(fontSize: 13, color: Colors.black87))),
        ],
      ),
    );
  }
}
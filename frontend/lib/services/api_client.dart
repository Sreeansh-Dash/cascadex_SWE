/// Typed HTTP Client for CascadeX backend API using Dio.
///
/// Features:
/// - Automatic JWT Bearer token injection
/// - Caregiver proxy header injection (`X-Caregiver-Target-User`)
/// - Automatic 401 refresh token rotation
/// - Comprehensive typed API methods for all Phase 03-08 endpoints
library;

import 'dart:io';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

import 'secure_storage.dart';

class ApiException implements Exception {
  final int? statusCode;
  final String code;
  final String message;
  final dynamic rawData;

  ApiException({
    this.statusCode,
    required this.code,
    required this.message,
    this.rawData,
  });

  @override
  String toString() => 'ApiException [$statusCode | $code]: $message';
}

class ApiClient {
  final Dio dio;
  final SecureStorageService secureStorage;

  static String get defaultBaseUrl {
    if (kIsWeb) return 'http://localhost:8000/api/v1';
    if (Platform.isAndroid) return 'http://10.0.2.2:8000/api/v1';
    return 'http://localhost:8000/api/v1';
  }

  ApiClient({
    String? baseUrl,
    Dio? customDio,
    SecureStorageService? storage,
  })  : secureStorage = storage ?? SecureStorageService(),
        dio = customDio ??
            Dio(
              BaseOptions(
                baseUrl: baseUrl ?? defaultBaseUrl,
                connectTimeout: const Duration(seconds: 15),
                receiveTimeout: const Duration(seconds: 15),
                headers: {
                  'Content-Type': 'application/json',
                  'Accept': 'application/json',
                },
              ),
            ) {
    _setupInterceptors();
  }

  void _setupInterceptors() {
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          // Attach JWT token if present
          final token = await secureStorage.getAccessToken();
          if (token != null && token.isNotEmpty) {
            options.headers['Authorization'] = 'Bearer $token';
          }

          // Attach caregiver target user header if in caregiver mode
          final targetUser = await secureStorage.getCaregiverTargetUser();
          if (targetUser != null && targetUser.isNotEmpty) {
            options.headers['X-Caregiver-Target-User'] = targetUser;
          }

          return handler.next(options);
        },
        onError: (DioException error, handler) async {
          // Handle 401 Refresh Token rotation
          if (error.response?.statusCode == 401 &&
              error.requestOptions.path != '/auth/login' &&
              error.requestOptions.path != '/auth/refresh') {
            final refreshed = await _attemptTokenRefresh();
            if (refreshed) {
              // Retry original request with new token
              final opts = error.requestOptions;
              final newToken = await secureStorage.getAccessToken();
              opts.headers['Authorization'] = 'Bearer $newToken';
              try {
                final response = await dio.fetch(opts);
                return handler.resolve(response);
              } catch (e) {
                // fall through
              }
            }
          }
          return handler.next(error);
        },
      ),
    );
  }

  Future<bool> _attemptTokenRefresh() async {
    try {
      final refreshToken = await secureStorage.getRefreshToken();
      if (refreshToken == null) return false;

      final res = await dio.post(
        '/auth/refresh',
        data: {'refresh_token': refreshToken},
        options: Options(headers: {'Authorization': null}),
      );

      if (res.statusCode == 200) {
        final data = res.data as Map<String, dynamic>;
        final newAccess = data['access_token'] as String;
        final newRefresh = data['refresh_token'] as String;
        final userId = await secureStorage.getUserId() ?? '';
        final role = await secureStorage.getRole() ?? 'user';
        await secureStorage.saveAuthTokens(
          accessToken: newAccess,
          refreshToken: newRefresh,
          userId: userId,
          role: role,
        );
        return true;
      }
    } catch (e) {
      debugPrint('Token refresh failed: $e');
    }
    return false;
  }

  ApiException _handleError(dynamic error) {
    if (error is DioException) {
      final res = error.response;
      if (res?.data is Map) {
        final data = res!.data as Map;
        final detail = data['detail'];
        if (detail is Map) {
          return ApiException(
            statusCode: res.statusCode,
            code: detail['code']?.toString() ?? 'error',
            message: detail['message']?.toString() ?? error.message ?? 'Unknown error',
            rawData: res.data,
          );
        } else if (detail is String) {
          return ApiException(
            statusCode: res.statusCode,
            code: 'error',
            message: detail,
            rawData: res.data,
          );
        }
      }
      return ApiException(
        statusCode: res?.statusCode,
        code: 'network_error',
        message: error.message ?? 'Network communication error',
        rawData: res?.data,
      );
    }
    return ApiException(code: 'unknown', message: error.toString());
  }

  // ---------------------------------------------------------------------------
  // Auth Endpoints
  // ---------------------------------------------------------------------------

  Future<Map<String, dynamic>> register({
    required String fullName,
    required String dateOfBirth,
    String? email,
    String? phoneNumber,
    required String password,
  }) async {
    try {
      final res = await dio.post(
        '/auth/register',
        data: {
          'full_name': fullName,
          'date_of_birth': dateOfBirth,
          if (email != null && email.isNotEmpty) 'email': email,
          if (phoneNumber != null && phoneNumber.isNotEmpty) 'phone_number': phoneNumber,
          'password': password,
        },
      );
      return Map<String, dynamic>.from(res.data as Map);
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<Map<String, dynamic>> login({
    required String emailOrPhone,
    required String password,
  }) async {
    try {
      final res = await dio.post(
        '/auth/login',
        data: {
          'email_or_phone': emailOrPhone,
          'password': password,
        },
      );
      return Map<String, dynamic>.from(res.data as Map);
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<Map<String, dynamic>> linkCaregiver({
    required String caregiverEmailOrPhone,
    required String permissionLevel, // 'view_only' | 'manage'
    String? relationshipToUser,
  }) async {
    try {
      final res = await dio.post(
        '/auth/caregivers',
        data: {
          'caregiver_email_or_phone': caregiverEmailOrPhone,
          'permission_level': permissionLevel,
          if (relationshipToUser != null) 'relationship_to_user': relationshipToUser,
        },
      );
      return Map<String, dynamic>.from(res.data as Map);
    } catch (e) {
      throw _handleError(e);
    }
  }

  // ---------------------------------------------------------------------------
  // Drug Catalog & Medications Endpoints
  // ---------------------------------------------------------------------------

  Future<List<Map<String, dynamic>>> searchDrugs({
    required String query,
    int limit = 20,
    int offset = 0,
  }) async {
    try {
      final res = await dio.get(
        '/drugs/search',
        queryParameters: {'q': query, 'limit': limit, 'offset': offset},
      );
      final list = res.data as List;
      return list.map((e) => Map<String, dynamic>.from(e as Map)).toList();
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<Map<String, dynamic>> addMedication({
    required String drugId,
    required double dosageAmount,
    required String dosageUnit,
    required List<Map<String, dynamic>> schedules,
    String? notes,
    String inputMethod = 'manual',
  }) async {
    try {
      final res = await dio.post(
        '/medications',
        data: {
          'drug_id': drugId,
          'dosage_amount': dosageAmount,
          'dosage_unit': dosageUnit,
          'schedules': schedules,
          if (notes != null) 'notes': notes,
          'input_method': inputMethod,
        },
      );
      return Map<String, dynamic>.from(res.data as Map);
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<List<Map<String, dynamic>>> listMedications({
    bool includeInactive = false,
  }) async {
    try {
      final res = await dio.get(
        '/medications',
        queryParameters: {'include_inactive': includeInactive},
      );
      final list = res.data as List;
      return list.map((e) => Map<String, dynamic>.from(e as Map)).toList();
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<Map<String, dynamic>> patchMedication(
    String entryId, {
    double? dosageAmount,
    String? dosageUnit,
    String? notes,
    List<Map<String, dynamic>>? schedules,
    bool deactivate = false,
  }) async {
    try {
      final res = await dio.patch(
        '/medications/$entryId',
        data: {
          if (dosageAmount != null) 'dosage_amount': dosageAmount,
          if (dosageUnit != null) 'dosage_unit': dosageUnit,
          if (notes != null) 'notes': notes,
          if (schedules != null) 'schedules': schedules,
          'deactivate': deactivate,
        },
      );
      return Map<String, dynamic>.from(res.data as Map);
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<Map<String, dynamic>> logDose(
    String entryId, {
    required String status, // 'taken' | 'missed' | 'skipped'
    required String scheduledTime,
    String? takenAt,
    String? notes,
  }) async {
    try {
      final res = await dio.post(
        '/medications/$entryId/doses',
        data: {
          'status': status,
          'scheduled_time': scheduledTime,
          if (takenAt != null) 'taken_at': takenAt,
          if (notes != null) 'notes': notes,
        },
      );
      return Map<String, dynamic>.from(res.data as Map);
    } catch (e) {
      throw _handleError(e);
    }
  }

  // ---------------------------------------------------------------------------
  // Alerts Endpoints
  // ---------------------------------------------------------------------------

  Future<List<Map<String, dynamic>>> listAlerts({
    bool? acknowledged,
    int limit = 50,
    int offset = 0,
  }) async {
    try {
      final queryParams = <String, dynamic>{'limit': limit, 'offset': offset};
      if (acknowledged != null) queryParams['acknowledged'] = acknowledged;

      final res = await dio.get('/alerts', queryParameters: queryParams);
      final list = res.data as List;
      return list.map((e) => Map<String, dynamic>.from(e as Map)).toList();
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<Map<String, dynamic>> acknowledgeAlert(String alertId) async {
    try {
      final res = await dio.post('/alerts/$alertId/acknowledge');
      return Map<String, dynamic>.from(res.data as Map);
    } catch (e) {
      throw _handleError(e);
    }
  }

  // ---------------------------------------------------------------------------
  // History & PDF Export Endpoints
  // ---------------------------------------------------------------------------

  Future<Map<String, dynamic>> getHistoryFeed({
    String? before,
    int limit = 20,
  }) async {
    try {
      final queryParams = <String, dynamic>{'limit': limit};
      if (before != null) queryParams['before'] = before;

      final res = await dio.get('/history', queryParameters: queryParams);
      return Map<String, dynamic>.from(res.data as Map);
    } catch (e) {
      throw _handleError(e);
    }
  }

  Future<List<int>> exportHistoryPdf() async {
    try {
      final res = await dio.get<List<int>>(
        '/history/export',
        options: Options(responseType: ResponseType.bytes),
      );
      return res.data ?? [];
    } catch (e) {
      throw _handleError(e);
    }
  }

  // ---------------------------------------------------------------------------
  // Health & Diagnostics
  // ---------------------------------------------------------------------------

  Future<Map<String, dynamic>> getHealth() async {
    try {
      final res = await dio.get('/health');
      return Map<String, dynamic>.from(res.data as Map);
    } catch (e) {
      throw _handleError(e);
    }
  }
}

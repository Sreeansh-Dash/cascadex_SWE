/// Authentication State Provider using Riverpod.
///
/// Handles:
/// - Login (email/phone + password)
/// - Registration
/// - Token restoration from secure storage on startup
/// - Caregiver target switching
/// - Logout & session cleanup
library;

import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/api_client.dart';
import '../services/secure_storage.dart';

/// Decode a JWT token and return its payload as a Map.
/// The JWT payload is the second dot-separated base64url segment.
Map<String, dynamic> _decodeJwtPayload(String token) {
  final parts = token.split('.');
  if (parts.length != 3) throw const FormatException('Invalid JWT structure');
  // base64url → base64 padding
  String normalized = parts[1].replaceAll('-', '+').replaceAll('_', '/');
  switch (normalized.length % 4) {
    case 2:
      normalized += '==';
      break;
    case 3:
      normalized += '=';
      break;
    default:
      break;
  }
  final decoded = utf8.decode(base64.decode(normalized));
  return json.decode(decoded) as Map<String, dynamic>;
}

class AuthState {
  final bool isLoading;
  final bool isAuthenticated;
  final String? userId;
  final String? accessToken;
  final String? userRole; // 'user' | 'caregiver'
  final String? caregiverTargetUserId;
  final String? errorMessage;

  const AuthState({
    this.isLoading = false,
    this.isAuthenticated = false,
    this.userId,
    this.accessToken,
    this.userRole,
    this.caregiverTargetUserId,
    this.errorMessage,
  });

  AuthState copyWith({
    bool? isLoading,
    bool? isAuthenticated,
    String? userId,
    String? accessToken,
    String? userRole,
    String? caregiverTargetUserId,
    String? errorMessage,
  }) {
    return AuthState(
      isLoading: isLoading ?? this.isLoading,
      isAuthenticated: isAuthenticated ?? this.isAuthenticated,
      userId: userId ?? this.userId,
      accessToken: accessToken ?? this.accessToken,
      userRole: userRole ?? this.userRole,
      caregiverTargetUserId: caregiverTargetUserId ?? this.caregiverTargetUserId,
      errorMessage: errorMessage,
    );
  }
}

class AuthNotifier extends StateNotifier<AuthState> {
  final ApiClient _apiClient;
  final SecureStorageService _secureStorage;

  AuthNotifier({
    ApiClient? apiClient,
    SecureStorageService? secureStorage,
  })  : _secureStorage = secureStorage ?? SecureStorageService(),
        _apiClient = apiClient ?? ApiClient(storage: secureStorage),
        super(const AuthState(isLoading: true)) {
    checkInitialAuth();
  }

  Future<void> checkInitialAuth() async {
    state = state.copyWith(isLoading: true, errorMessage: null);
    try {
      final token = await _secureStorage.getAccessToken();
      final userId = await _secureStorage.getUserId();
      final role = await _secureStorage.getRole();
      final target = await _secureStorage.getCaregiverTargetUser();

      if (token != null && token.isNotEmpty && userId != null) {
        state = state.copyWith(
          isLoading: false,
          isAuthenticated: true,
          userId: userId,
          accessToken: token,
          userRole: role ?? 'user',
          caregiverTargetUserId: target,
        );
      } else {
        state = const AuthState(isLoading: false, isAuthenticated: false);
      }
    } catch (e) {
      state = const AuthState(isLoading: false, isAuthenticated: false);
    }
  }

  Future<bool> login({
    required String emailOrPhone,
    required String password,
  }) async {
    state = state.copyWith(isLoading: true, errorMessage: null);
    try {
      final data = await _apiClient.login(
        emailOrPhone: emailOrPhone,
        password: password,
      );

      final accessToken = data['access_token'] as String;
      final refreshToken = data['refresh_token'] as String;

      // The backend's TokenPair does not include user_id/role directly.
      // Decode them from the JWT access token payload (sub = account_id, role = role).
      final payload = _decodeJwtPayload(accessToken);
      final userId = payload['sub'] as String? ?? '';
      final role = payload['role'] as String? ?? 'user';

      await _secureStorage.saveAuthTokens(
        accessToken: accessToken,
        refreshToken: refreshToken,
        userId: userId,
        role: role,
      );

      state = state.copyWith(
        isLoading: false,
        isAuthenticated: true,
        userId: userId,
        userRole: role,
        errorMessage: null,
      );
      return true;
    } catch (e) {
      final msg = e is ApiException ? e.message : e.toString();
      state = state.copyWith(isLoading: false, errorMessage: msg);
      return false;
    }
  }

  Future<bool> register({
    required String fullName,
    required String dateOfBirth,
    String? email,
    String? phoneNumber,
    required String password,
  }) async {
    state = state.copyWith(isLoading: true, errorMessage: null);
    try {
      await _apiClient.register(
        fullName: fullName,
        dateOfBirth: dateOfBirth,
        email: email,
        phoneNumber: phoneNumber,
        password: password,
      );

      // Auto-login after registration
      final credential = (email != null && email.isNotEmpty) ? email : phoneNumber!;
      return await login(emailOrPhone: credential, password: password);
    } catch (e) {
      final msg = e is ApiException ? e.message : e.toString();
      state = state.copyWith(isLoading: false, errorMessage: msg);
      return false;
    }
  }

  Future<void> setCaregiverTargetUser(String? targetUserId) async {
    await _secureStorage.setCaregiverTargetUser(targetUserId);
    state = state.copyWith(caregiverTargetUserId: targetUserId);
  }

  Future<void> logout() async {
    await _secureStorage.clearAll();
    state = const AuthState(isLoading: false, isAuthenticated: false);
  }
}

final secureStorageProvider = Provider<SecureStorageService>((ref) {
  return SecureStorageService();
});

final apiClientProvider = Provider<ApiClient>((ref) {
  final storage = ref.watch(secureStorageProvider);
  return ApiClient(storage: storage);
});

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  final client = ref.watch(apiClientProvider);
  final storage = ref.watch(secureStorageProvider);
  return AuthNotifier(apiClient: client, secureStorage: storage);
});

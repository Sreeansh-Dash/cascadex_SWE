/// Secure token and session storage using `flutter_secure_storage`.
///
/// Encrypts JWT access & refresh tokens on-device (Android Keystore / iOS Keychain).
/// Never stores tokens in plain SharedPreferences.
library;

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class SecureStorageService {
  static const _kAccessToken = 'access_token';
  static const _kRefreshToken = 'refresh_token';
  static const _kUserId = 'user_id';
  static const _kRole = 'user_role';
  static const _kCaregiverTargetUserId = 'caregiver_target_user_id';

  final FlutterSecureStorage _storage;

  SecureStorageService([FlutterSecureStorage? storage])
      : _storage = storage ?? const FlutterSecureStorage();

  Future<void> saveAuthTokens({
    required String accessToken,
    required String refreshToken,
    required String userId,
    String role = 'user',
  }) async {
    await _storage.write(key: _kAccessToken, value: accessToken);
    await _storage.write(key: _kRefreshToken, value: refreshToken);
    await _storage.write(key: _kUserId, value: userId);
    await _storage.write(key: _kRole, value: role);
  }

  Future<String?> getAccessToken() async => _storage.read(key: _kAccessToken);

  Future<String?> getRefreshToken() async => _storage.read(key: _kRefreshToken);

  Future<String?> getUserId() async => _storage.read(key: _kUserId);

  Future<String?> getRole() async => _storage.read(key: _kRole);

  Future<void> setCaregiverTargetUser(String? targetUserId) async {
    if (targetUserId == null) {
      await _storage.delete(key: _kCaregiverTargetUserId);
    } else {
      await _storage.write(key: _kCaregiverTargetUserId, value: targetUserId);
    }
  }

  Future<String?> getCaregiverTargetUser() async =>
      _storage.read(key: _kCaregiverTargetUserId);

  Future<void> clearAll() async {
    await _storage.deleteAll();
  }
}

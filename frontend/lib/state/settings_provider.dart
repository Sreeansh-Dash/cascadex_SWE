/// Settings & Accessibility State Management Provider using Riverpod.
///
/// Features:
/// - Text font scale factor preference (1.0, 1.25, 1.5)
/// - Caregiver linking and listing
library;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/api_client.dart';
import 'auth_provider.dart';

class SettingsState {
  final double fontScale;
  final bool isLoading;
  final List<Map<String, dynamic>> linkedCaregivers;
  final String? errorMessage;
  final String? successMessage;

  const SettingsState({
    this.fontScale = 1.0,
    this.isLoading = false,
    this.linkedCaregivers = const [],
    this.errorMessage,
    this.successMessage,
  });

  SettingsState copyWith({
    double? fontScale,
    bool? isLoading,
    List<Map<String, dynamic>>? linkedCaregivers,
    String? errorMessage,
    String? successMessage,
  }) {
    return SettingsState(
      fontScale: fontScale ?? this.fontScale,
      isLoading: isLoading ?? this.isLoading,
      linkedCaregivers: linkedCaregivers ?? this.linkedCaregivers,
      errorMessage: errorMessage,
      successMessage: successMessage,
    );
  }
}

class SettingsNotifier extends StateNotifier<SettingsState> {
  final ApiClient _apiClient;

  SettingsNotifier({required ApiClient apiClient})
      : _apiClient = apiClient,
        super(const SettingsState());

  void setFontScale(double scale) {
    state = state.copyWith(fontScale: scale);
  }

  Future<bool> linkCaregiver({
    required String emailOrPhone,
    required String permissionLevel,
    String? relationship,
  }) async {
    state = state.copyWith(isLoading: true, errorMessage: null, successMessage: null);
    try {
      final res = await _apiClient.linkCaregiver(
        caregiverEmailOrPhone: emailOrPhone,
        permissionLevel: permissionLevel,
        relationshipToUser: relationship,
      );

      state = state.copyWith(
        isLoading: false,
        linkedCaregivers: [...state.linkedCaregivers, res],
        successMessage: 'Caregiver linked successfully',
      );
      return true;
    } catch (e) {
      final msg = e is ApiException ? e.message : e.toString();
      state = state.copyWith(isLoading: false, errorMessage: msg);
      return false;
    }
  }
}

final settingsProvider = StateNotifierProvider<SettingsNotifier, SettingsState>((ref) {
  final client = ref.watch(apiClientProvider);
  return SettingsNotifier(apiClient: client);
});

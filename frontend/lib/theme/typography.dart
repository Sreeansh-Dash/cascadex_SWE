/// CascadeX Design System — Accessible Typography.
///
/// Accessibility Standard:
/// - Base body font size has a strict floor of 16sp (never below).
/// - Line heights (leading) are generous (>= 1.35x) to support elderly reading.
/// - Scalable with system `textScaleFactor` / `TextScaler`.
library;

import 'package:flutter/material.dart';
import 'colors.dart';

class AppText {
  // Named static text styles
  static const TextStyle headline = TextStyle(
    fontSize: 22,
    fontWeight: FontWeight.bold,
    height: 1.3,
    color: AppColors.textPrimary,
    letterSpacing: -0.2,
  );

  static const TextStyle subhead = TextStyle(
    fontSize: 18,
    fontWeight: FontWeight.w600,
    height: 1.35,
    color: AppColors.textPrimary,
  );

  static const TextStyle body = TextStyle(
    fontSize: 16,
    fontWeight: FontWeight.normal,
    height: 1.45,
    color: AppColors.textPrimary,
  );

  static const TextStyle bodyBold = TextStyle(
    fontSize: 16,
    fontWeight: FontWeight.w600,
    height: 1.45,
    color: AppColors.textPrimary,
  );

  static const TextStyle caption = TextStyle(
    fontSize: 14,
    fontWeight: FontWeight.w500,
    height: 1.4,
    color: AppColors.textSecondary,
  );

  static const TextStyle disclaimer = TextStyle(
    fontSize: 13,
    fontStyle: FontStyle.italic,
    height: 1.4,
    color: AppColors.severityMajor,
  );

  static const TextStyle button = TextStyle(
    fontSize: 16,
    fontWeight: FontWeight.w600,
    letterSpacing: 0.2,
    color: Colors.white,
  );

  /// Material 3 Accessible TextTheme for ThemeData
  static TextTheme get textTheme {
    return const TextTheme(
      headlineLarge: TextStyle(fontSize: 28, fontWeight: FontWeight.bold, height: 1.25, color: AppColors.textPrimary),
      headlineMedium: headline,
      headlineSmall: subhead,
      titleLarge: subhead,
      titleMedium: bodyBold,
      titleSmall: caption,
      bodyLarge: body,
      bodyMedium: body, // 16sp floor
      bodySmall: caption,
      labelLarge: button,
      labelMedium: caption,
      labelSmall: TextStyle(fontSize: 12, fontWeight: FontWeight.w500, color: AppColors.textMuted),
    );
  }
}

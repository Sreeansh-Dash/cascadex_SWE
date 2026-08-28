/// SeverityBadge — Color-blind safe severity indicator.
///
/// Design Rules:
/// - Never relies on color alone (combines color, icon, and explicit text label).
/// - High WCAG AA contrast ratio (> 4.5:1) in all variations.
/// - Integrated Semantics for screen readers.
library;

import 'package:flutter/material.dart';
import '../theme/colors.dart';

enum AlertSeverityLevel {
  major,
  moderate,
  minor,
  none,
}

class SeverityBadge extends StatelessWidget {
  final String? rawSeverity; // 'major' | 'moderate' | 'minor'
  final bool isClean;
  final bool isCompact;

  const SeverityBadge({
    super.key,
    this.rawSeverity,
    this.isClean = false,
    this.isCompact = false,
  });

  AlertSeverityLevel get _level {
    if (isClean) return AlertSeverityLevel.none;
    switch (rawSeverity?.toLowerCase().trim()) {
      case 'major':
        return AlertSeverityLevel.major;
      case 'moderate':
        return AlertSeverityLevel.moderate;
      case 'minor':
        return AlertSeverityLevel.minor;
      default:
        return AlertSeverityLevel.none;
    }
  }

  @override
  Widget build(BuildContext context) {
    Color bg;
    Color border;
    Color fg;
    IconData icon;
    String label;
    String semanticDescription;

    switch (_level) {
      case AlertSeverityLevel.major:
        bg = AppColors.severityMajorBg;
        border = AppColors.severityMajor;
        fg = AppColors.severityMajor;
        icon = Icons.dangerous_rounded;
        label = 'MAJOR INTERACTION';
        semanticDescription = 'Warning: Major drug interaction detected. Doctor consultation required.';
        break;
      case AlertSeverityLevel.moderate:
        bg = AppColors.severityModerateBg;
        border = AppColors.severityModerate;
        fg = AppColors.severityModerate;
        icon = Icons.warning_amber_rounded;
        label = 'MODERATE INTERACTION';
        semanticDescription = 'Notice: Moderate drug interaction detected. Monitor symptoms closely.';
        break;
      case AlertSeverityLevel.minor:
        bg = AppColors.severityMinorBg;
        border = AppColors.severityMinor;
        fg = AppColors.severityMinorText;
        icon = Icons.info_outline_rounded;
        label = 'MINOR INTERACTION';
        semanticDescription = 'Advisory: Minor drug interaction detected.';
        break;
      case AlertSeverityLevel.none:
        bg = AppColors.successBg;
        border = AppColors.success;
        fg = AppColors.success;
        icon = Icons.check_circle_outline_rounded;
        label = 'NO INTERACTIONS FOUND';
        semanticDescription = 'All clear: No known drug interactions found.';
        break;
    }

    if (isCompact) {
      return Semantics(
        label: semanticDescription,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: bg,
            borderRadius: BorderRadius.circular(6),
            border: Border.all(color: border, width: 1),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 16, color: fg),
              const SizedBox(width: 4),
              Text(
                label,
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                  color: fg,
                  letterSpacing: 0.2,
                ),
              ),
            ],
          ),
        ),
      );
    }

    return Semantics(
      label: semanticDescription,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: bg,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: border, width: 1.5),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 22, color: fg),
            const SizedBox(width: 8),
            Text(
              label,
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.bold,
                color: fg,
                letterSpacing: 0.3,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

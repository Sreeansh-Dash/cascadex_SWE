/// DisclaimerBanner — Mandatory Clinical Safety Disclaimer Widget.
///
/// Reused across all alert, scan, medication, and onboarding screens.
library;

import 'package:flutter/material.dart';
import '../theme/colors.dart';
import '../theme/typography.dart';

class DisclaimerBanner extends StatelessWidget {
  final String? customText;
  final bool isCompact;

  const DisclaimerBanner({
    super.key,
    this.customText,
    this.isCompact = false,
  });

  static const String defaultDisclaimer =
      'CascadeX is an academic software demonstration and not a certified medical device. '
      'Always consult your pharmacist or doctor before taking or altering any medication.';

  @override
  Widget build(BuildContext context) {
    final text = customText ?? defaultDisclaimer;

    return Semantics(
      label: 'Important medical disclaimer: $text',
      child: Container(
        padding: EdgeInsets.symmetric(
          horizontal: isCompact ? 12 : 16,
          vertical: isCompact ? 8 : 12,
        ),
        decoration: BoxDecoration(
          color: AppColors.severityMajorBg,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: AppColors.severityMajor.withOpacity(0.4), width: 1),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Icon(
              Icons.warning_amber_rounded,
              color: AppColors.severityMajor,
              size: 22,
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                text,
                style: AppText.disclaimer.copyWith(
                  fontSize: isCompact ? 12 : 13,
                  color: AppColors.severityMajor,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

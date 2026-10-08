/// OfflineBanner — Informs the user when operating in offline/cached mode.
library;

import 'package:flutter/material.dart';
import '../theme/colors.dart';

class OfflineBanner extends StatelessWidget {
  final VoidCallback? onRetry;

  const OfflineBanner({super.key, this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      color: AppColors.offlineBg,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          const Icon(Icons.cloud_off_rounded, color: AppColors.offlineText, size: 20),
          const SizedBox(width: 10),
          const Expanded(
            child: Text(
              'Using saved data while we reconnect. Your changes will sync when you are online.',
              style: TextStyle(
                color: AppColors.offlineText,
                fontSize: 13,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
          if (onRetry != null)
            TextButton(
              onPressed: onRetry,
              style: TextButton.styleFrom(
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(horizontal: 8),
              ),
              child: const Text('Retry connection', style: TextStyle(fontWeight: FontWeight.bold)),
            ),
        ],
      ),
    );
  }
}

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
              'Offline mode — using cached medical data. Changes will sync once reconnected.',
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
              child: const Text('RETRY', style: TextStyle(fontWeight: FontWeight.bold)),
            ),
        ],
      ),
    );
  }
}

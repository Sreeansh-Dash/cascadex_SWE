/// Alert detail screen — Phase 01 placeholder.
///
/// Phase 07 builds this screen with full alert detail, severity badge,
/// plain-language explanation, and acknowledgement flow.
///
/// ⚠️ Every alert screen must carry the disclaimer:
/// "This is not a substitute for advice from a pharmacist or doctor."
library;

import 'package:flutter/material.dart';

class AlertDetailScreen extends StatelessWidget {
  const AlertDetailScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Interaction Alert'),
      ),
      body: const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.warning_amber_rounded, size: 64, color: Colors.orange),
            SizedBox(height: 16),
            Text(
              'Phase 07 builds this screen',
              style: TextStyle(fontSize: 18),
            ),
            SizedBox(height: 8),
            Text(
              'Alert Detail + Acknowledgement',
              style: TextStyle(color: Colors.grey),
            ),
            SizedBox(height: 24),
            Padding(
              padding: EdgeInsets.symmetric(horizontal: 32),
              child: Text(
                '⚠️ Not a substitute for advice from a pharmacist or doctor.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 12, color: Colors.red),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

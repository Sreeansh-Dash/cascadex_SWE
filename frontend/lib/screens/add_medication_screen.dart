/// Add medication screen — Phase 01 placeholder.
///
/// Phase 04 builds this screen with catalog search + dose schedule entry.
library;

import 'package:flutter/material.dart';

class AddMedicationScreen extends StatelessWidget {
  const AddMedicationScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Add Medication'),
      ),
      body: const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.add_circle_outline, size: 64, color: Colors.blueAccent),
            SizedBox(height: 16),
            Text(
              'Phase 04 builds this screen',
              style: TextStyle(fontSize: 18),
            ),
            SizedBox(height: 8),
            Text(
              'Catalog Search & Manual Entry',
              style: TextStyle(color: Colors.grey),
            ),
          ],
        ),
      ),
    );
  }
}

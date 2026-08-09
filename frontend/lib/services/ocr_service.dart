/// CascadeX OCR Service — Phase 05.
///
/// Wraps `google_mlkit_text_recognition` for on-device text extraction.
/// The raw camera image never leaves the device; only the extracted text
/// string is sent to `POST /api/v1/scans` on the backend.
///
/// Usage:
/// ```dart
/// final result = await OcrService().extractAndMatch(imagePath);
/// ```
library;

import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:google_mlkit_text_recognition/google_mlkit_text_recognition.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

/// Result returned by [OcrService.extractAndMatch].
class OcrScanResult {
  /// Raw text extracted on-device by ML Kit (before backend match).
  final String ocrText;

  /// The `scan_id` from the backend's `ScanRecord`.
  final String scanId;

  /// Match status: `"matched"`, `"unmatched"`, or `"pending"`.
  final String status;

  /// Best single candidate from the backend pipeline, or `null`.
  final Map<String, dynamic>? primaryMatch;

  /// All candidate drugs returned by the backend.
  final List<Map<String, dynamic>> candidates;

  /// Human-readable hint for the confirmation screen.
  final String message;

  const OcrScanResult({
    required this.ocrText,
    required this.scanId,
    required this.status,
    this.primaryMatch,
    this.candidates = const [],
    this.message = '',
  });
}

/// Service that runs on-device OCR and submits the result to the backend.
class OcrService {
  /// Base URL for the backend API. Override for testing.
  final String baseUrl;

  /// JWT Bearer token for the authenticated user.
  final String accessToken;

  OcrService({
    required this.accessToken,
    this.baseUrl = 'http://10.0.2.2:8000/api/v1', // Android emulator default
  });

  /// Extract text from [imagePath] using ML Kit, then submit to `POST /scans`.
  ///
  /// Returns an [OcrScanResult] with candidates for the confirmation screen.
  /// Throws on network failure; caller should show an error and let the user retry.
  ///
  /// Privacy: the image is processed locally; only [ocrText] leaves the device.
  Future<OcrScanResult> extractAndMatch(String imagePath) async {
    // ── Step 1: On-device OCR ─────────────────────────────────────────────
    final rawText = await _runMlKitOcr(imagePath);
    debugPrint('OcrService: extracted text="${rawText.substring(0, rawText.length.clamp(0, 80))}..."');

    if (rawText.trim().isEmpty) {
      // No text found — return gracefully so the UI can show a retry prompt.
      return OcrScanResult(
        ocrText: rawText,
        scanId: '',
        status: 'unmatched',
        message: 'No text detected. Please try scanning again with better lighting.',
      );
    }

    // ── Step 2: Submit to backend ─────────────────────────────────────────
    return submitText(rawText);
  }

  /// Submit a raw text string (typed or pre-extracted) directly to `POST /scans`.
  ///
  /// Useful when the user types a drug name manually instead of scanning.
  Future<OcrScanResult> submitText(String text) => _postScan(text);

  // ---------------------------------------------------------------------------
  // Private helpers
  // ---------------------------------------------------------------------------

  /// Run ML Kit text recogniser on the given image file.
  Future<String> _runMlKitOcr(String imagePath) async {
    final inputImage = InputImage.fromFilePath(imagePath);
    final textRecognizer = TextRecognizer(script: TextRecognitionScript.latin);
    try {
      final recognised = await textRecognizer.processImage(inputImage);
      return recognised.text;
    } finally {
      textRecognizer.close();
    }
  }

  /// POST extracted text to `POST /scans` and parse the response.
  Future<OcrScanResult> _postScan(String ocrText) async {
    final uri = Uri.parse('$baseUrl/scans');
    final response = await http.post(
      uri,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $accessToken',
      },
      body: jsonEncode({'ocr_text': ocrText}),
    );

    if (response.statusCode != 201) {
      throw OcrServiceException(
        'Backend returned ${response.statusCode}: ${response.body}',
      );
    }

    final body = jsonDecode(response.body) as Map<String, dynamic>;
    final rawCandidates = (body['candidates'] as List<dynamic>?) ?? [];
    return OcrScanResult(
      ocrText: body['ocr_text'] as String? ?? ocrText,
      scanId: body['scan_id'] as String? ?? '',
      status: body['status'] as String? ?? 'unmatched',
      primaryMatch: body['primary_match'] as Map<String, dynamic>?,
      candidates: rawCandidates.cast<Map<String, dynamic>>(),
      message: body['message'] as String? ?? '',
    );
  }
}

/// Thrown by [OcrService] on backend communication errors.
class OcrServiceException implements Exception {
  final String message;
  const OcrServiceException(this.message);

  @override
  String toString() => 'OcrServiceException: $message';
}

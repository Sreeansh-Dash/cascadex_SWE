/// AccessibleText — Text wrapper enforcing font scaling & minimum 16sp floor.
library;

import 'package:flutter/material.dart';
import '../theme/colors.dart';

class AccessibleText extends StatelessWidget {
  final String text;
  final TextStyle? style;
  final TextAlign? textAlign;
  final int? maxLines;
  final TextOverflow? overflow;
  final double minFontSize;

  const AccessibleText(
    this.text, {
    super.key,
    this.style,
    this.textAlign,
    this.maxLines,
    this.overflow,
    this.minFontSize = 16.0,
  });

  @override
  Widget build(BuildContext context) {
    final baseStyle = style ?? const TextStyle(fontSize: 16.0, color: AppColors.textPrimary);
    final effectiveFontSize = (baseStyle.fontSize ?? 16.0) < minFontSize
        ? minFontSize
        : (baseStyle.fontSize ?? 16.0);

    return Text(
      text,
      textAlign: textAlign,
      maxLines: maxLines,
      overflow: overflow,
      style: baseStyle.copyWith(fontSize: effectiveFontSize),
    );
  }
}

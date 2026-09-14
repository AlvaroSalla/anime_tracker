import 'package:flutter/material.dart';

/// Imagen de portada con placeholder de carga y fallback de error.
///
/// Centraliza el uso de [Image.network] para no repetir
/// `loadingBuilder` / `errorBuilder` en cada pantalla.
class AnimeCoverImage extends StatelessWidget {
  /// URL de la imagen. Si es `null` o vacía, muestra el fallback
  /// de error directamente (sin intentar cargar nada).
  final String? url;

  final double width;
  final double height;

  /// Radio de las esquinas redondeadas.
  final double borderRadius;

  const AnimeCoverImage({
    super.key,
    required this.url,
    required this.width,
    required this.height,
    this.borderRadius = 8,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return ClipRRect(
      borderRadius: BorderRadius.circular(borderRadius),
      child: Container(
        width: width,
        height: height,
        color: scheme.surfaceContainerHighest,
        child: url == null || url!.isEmpty
            ? Icon(
                Icons.image_not_supported_outlined,
                color: scheme.onSurfaceVariant,
              )
            : Image.network(
                url!,
                width: width,
                height: height,
                fit: BoxFit.cover,
                loadingBuilder: (context, child, loadingProgress) {
                  if (loadingProgress == null) return child;
                  return const Center(
                    child: SizedBox(
                      width: 24,
                      height: 24,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                  );
                },
                errorBuilder: (context, error, stackTrace) {
                  return Icon(
                    Icons.broken_image_outlined,
                    color: scheme.onSurfaceVariant,
                  );
                },
              ),
      ),
    );
  }
}

import 'package:flutter/material.dart';

import '../models/anime.dart';
import 'anime_image.dart';

/// Card de anime para el carrusel horizontal: portada + título.
///
/// El tap por ahora solo deja un log de debug; la navegación al
/// detalle se agrega en el próximo módulo.
class AnimeCard extends StatelessWidget {
  final Anime anime;

  /// Si no se pasa, hace `debugPrint` con el id (placeholder hasta
  /// que exista la pantalla de detalle).
  final VoidCallback? onTap;

  const AnimeCard({super.key, required this.anime, this.onTap});

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return SizedBox(
      width: 140,
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap ?? () => debugPrint('Tap en anime id=${anime.id}'),
        child: Padding(
          padding: const EdgeInsets.all(4),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              AnimeCoverImage(
                url: anime.coverImageUrl,
                width: 132,
                height: 170,
                borderRadius: 12,
              ),
              const SizedBox(height: 6),
              Text(
                anime.tituloDisplay,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: textTheme.bodyMedium,
              ),
              const SizedBox(height: 2),
              Row(
                children: [
                  const Icon(Icons.star, size: 14, color: Colors.amber),
                  const SizedBox(width: 4),
                  Text(
                    anime.averageScore != null
                        ? '${anime.averageScore}'
                        : '—',
                    style: textTheme.bodySmall,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      anime.episodios != null
                          ? '${anime.episodios} eps'
                          : 'En emisión',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: textTheme.bodySmall,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

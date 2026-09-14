import 'package:flutter/material.dart';

import '../models/anime.dart';
import 'anime_image.dart';

/// Fila de anime para listas verticales: miniatura, título y score
/// con estrella alineado a la derecha.
class AnimeListTile extends StatelessWidget {
  final Anime anime;

  /// Si no se pasa, hace `debugPrint` con el id (placeholder hasta
  /// que exista la pantalla de detalle).
  final VoidCallback? onTap;

  const AnimeListTile({super.key, required this.anime, this.onTap});

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final subtitulo = [
      if (anime.generos.isNotEmpty) anime.generos.take(3).join(' • '),
      if (anime.seasonYear != null) '${anime.seasonYear}',
      if (anime.episodios != null) '${anime.episodios} eps' else 'En emisión',
    ].join('  ·  ');

    return ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      leading: AnimeCoverImage(
        url: anime.coverImageUrl,
        width: 48,
        height: 64,
      ),
      title: Text(
        anime.tituloDisplay,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
      ),
      subtitle: subtitulo.isEmpty
          ? null
          : Text(
              subtitulo,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
      trailing: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.star, size: 16, color: Colors.amber),
          const SizedBox(width: 4),
          Text(
            anime.averageScore != null ? '${anime.averageScore}' : '—',
            style: textTheme.bodyMedium,
          ),
        ],
      ),
      onTap: onTap ?? () => debugPrint('Tap en anime id=${anime.id}'),
    );
  }
}

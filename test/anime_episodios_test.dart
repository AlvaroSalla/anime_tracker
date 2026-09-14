import 'package:anime_tracker/models/anime.dart';
import 'package:flutter_test/flutter_test.dart';

/// Tests del campo `nextAiringEpisode` y de la inferencia de episodios
/// visibles para animes en emisión (total `null`).
void main() {
  group('Anime.fromJson', () {
    test('parsea nextAiringEpisode.episode', () {
      final anime = Anime.fromJson({
        'id': 1,
        'title': {'romaji': 'Airing', 'english': 'Airing'},
        'coverImage': {'large': 'https://example.com/a.jpg'},
        'genres': ['Action'],
        'averageScore': 80,
        'episodes': null,
        'nextAiringEpisode': {'episode': 8},
        'status': 'RELEASING',
      });

      expect(anime.episodios, isNull);
      expect(anime.proximoEpisodio, 8);
    });

    test('sin nextAiringEpisode queda null (no rompe)', () {
      final anime = Anime.fromJson({
        'id': 2,
        'title': {'romaji': 'Finished', 'english': 'Finished'},
        'episodes': 12,
        'status': 'FINISHED',
      });

      expect(anime.episodios, 12);
      expect(anime.proximoEpisodio, isNull);
    });
  });

  group('episodiosVisibles', () {
    test('finalizado: usa el total aunque haya progreso mayor', () {
      const anime = Anime(id: 2, episodios: 12, status: 'FINISHED');
      expect(anime.episodiosVisibles(0), 12);
      expect(anime.episodiosVisibles(5), 12);
    });

    test('en emisión: lista hasta nextAiring - 1', () {
      const anime = Anime(
        id: 1,
        episodios: null,
        proximoEpisodio: 8,
        status: 'RELEASING',
      );
      expect(anime.episodiosVisibles(0), 7);
    });

    test('en emisión: nunca esconde lo ya visto', () {
      const anime = Anime(
        id: 1,
        episodios: null,
        proximoEpisodio: 8,
        status: 'RELEASING',
      );
      expect(anime.episodiosVisibles(10), 10);
    });

    test('sin datos ni progreso: 0 (mostrar mensaje, no lista)', () {
      const anime = Anime(id: 3, episodios: null, status: 'RELEASING');
      expect(anime.episodiosVisibles(0), 0);
    });
  });
}

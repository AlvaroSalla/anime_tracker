import 'package:anime_tracker/models/anime.dart';
import 'package:anime_tracker/models/fuente_video.dart';
import 'package:anime_tracker/services/matching_service.dart';
import 'package:anime_tracker/services/scraper_service.dart';
import 'package:flutter_test/flutter_test.dart';

/// Fake en memoria de [ScraperService]: no pega a la red.
///
/// Devuelve listas canned por query exacta ([porQuery]) o la entrada
/// '*' como default. Registra las queries recibidas para verificar el
/// fallback romaji -> inglés.
class FakeScraperService extends ScraperService {
  final Map<String, List<ResultadoBusquedaFuente>> porQuery;
  final List<String> queries = [];

  FakeScraperService(this.porQuery);

  @override
  Future<List<ResultadoBusquedaFuente>> buscar(
    String query, {
    String sitio = 'animeflv',
  }) async {
    queries.add(query);
    return porQuery[query] ?? porQuery['*'] ?? const [];
  }
}

ResultadoBusquedaFuente fuente(String titulo, [String? slug]) =>
    ResultadoBusquedaFuente(
      titulo: titulo,
      slug: slug ?? titulo.toLowerCase().replaceAll(RegExp(r'\s+'), '-'),
      url: 'https://animeflv.or.at/anime/${slug ?? 'x'}/',
    );

void main() {
  test('título exacto se matchea automáticamente', () async {
    final scraper = FakeScraperService({
      'One Piece': [fuente('One Piece', 'one-piece')],
    });
    const anime = Anime(id: 21, tituloRomaji: 'One Piece');

    final resultado = await encontrarFuenteParaAnime(
      anime,
      scraper: scraper,
    );

    expect(resultado.tieneAutomatica, isTrue);
    expect(resultado.automatica!.titulo, 'One Piece');
    expect(resultado.automatica!.slug, 'one-piece');
    expect(scraper.queries, ['One Piece']);
  });

  test('mínimas diferencias (puntuación/tildes) igual matchean', () async {
    final scraper = FakeScraperService({
      // La fuente usa dos puntos y el AniList no (o viceversa).
      'Naruto Shippuden': [fuente('Naruto: Shippuden', 'naruto-shippuden')],
    });
    const anime = Anime(id: 1735, tituloRomaji: 'Naruto Shippuden');

    final resultado = await encontrarFuenteParaAnime(
      anime,
      scraper: scraper,
    );

    expect(resultado.tieneAutomatica, isTrue);
    expect(resultado.automatica!.titulo, 'Naruto: Shippuden');
  });

  test('sin resultados: sin automática y lista vacía', () async {
    final scraper = FakeScraperService({'*': const []});
    const anime = Anime(
      id: 999999,
      tituloRomaji: 'Anime Que No Existe 12345',
    );

    final resultado = await encontrarFuenteParaAnime(
      anime,
      scraper: scraper,
    );

    expect(resultado.tieneAutomatica, isFalse);
    expect(resultado.automatica, isNull);
    expect(resultado.candidatos, isEmpty);
  });

  test('varias coincidencias fuertes: ambiguo, no asume', () async {
    final scraper = FakeScraperService({
      'Naruto': [
        fuente('Naruto', 'naruto'),
        fuente('Naruto Shippuden', 'naruto-shippuden'),
      ],
    });
    const anime = Anime(id: 20, tituloRomaji: 'Naruto');

    final resultado = await encontrarFuenteParaAnime(
      anime,
      scraper: scraper,
    );

    // Ambos contienen al otro o son iguales -> ambiguo.
    expect(resultado.tieneAutomatica, isFalse);
    expect(resultado.automatica, isNull);
    expect(resultado.candidatos, hasLength(2));
  });

  test('romaji sin resultados reintenta con el inglés', () async {
    final scraper = FakeScraperService({
      'Shingeki no Kyojin': const [],
      'Attack on Titan': [fuente('Attack on Titan', 'attack-on-titan')],
    });
    const anime = Anime(
      id: 16498,
      tituloRomaji: 'Shingeki no Kyojin',
      tituloEnglish: 'Attack on Titan',
    );

    final resultado = await encontrarFuenteParaAnime(
      anime,
      scraper: scraper,
    );

    expect(scraper.queries, ['Shingeki no Kyojin', 'Attack on Titan']);
    expect(resultado.tieneAutomatica, isTrue);
    expect(resultado.automatica!.titulo, 'Attack on Titan');
  });
}

import 'package:anime_tracker/services/anilist_service.dart';
import 'package:flutter_test/flutter_test.dart';

/// Test de integración contra la API real de AniList.
///
/// Requiere conexión a internet. AniList tiene rate limit
/// (90 req/min), así que no abusar en CI.
void main() {
  late AnilistService service;

  setUp(() {
    service = AnilistService();
  });

  tearDown(() {
    service.dispose();
  });

  test('buscarAnime("Naruto") devuelve al menos un resultado válido', () async {
    final resultados = await service.buscarAnime('Naruto');

    // Al menos un resultado.
    expect(resultados, isNotEmpty);

    // Campos básicos completos en el primero.
    final primero = resultados.first;
    expect(primero.id, greaterThan(0));
    expect(primero.tituloDisplay, isNotEmpty);
    expect(
      primero.tituloRomaji ?? primero.tituloEnglish,
      isNotNull,
      reason: 'Debe tener al menos un título (romaji o inglés).',
    );
    expect(primero.coverImageUrl, isNotNull,
        reason: 'Debe traer URL de portada.');
  }, timeout: const Timeout(Duration(seconds: 30)));
}

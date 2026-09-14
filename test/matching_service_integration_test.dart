// ignore_for_file: avoid_print
// ═══════════════════════════════════════════════════════════════════════
// TEST DE INTEGRACIÓN MANUAL — REQUIERE EL SCRAPER-SERVICE CORRIENDO.
//
//   cd scraper-service && npm start   (http://localhost:3000)
//
// Usa el ScraperService REAL (sin mocks) contra AnimeFLV. Es una
// herramienta de inspección visual: imprime candidatos, scores y URL
// para revisar en consola. NO lo corras en CI sin el servicio.
//
// Falla SOLO si hay excepción de conexión (servicio apagado) o si la
// búsqueda devuelve vacío cuando debería traer algo. El matching
// automático en casos límite NO hace fallar el test a propósito.
//
// CÓMO CORRERLO (va con `skip` por default, no ensucia el run general):
//   flutter test                                     -> lo saltea (~skipped)
//   flutter test --tags integration --run-skipped    -> lo corre (requiere servicio)
// ═══════════════════════════════════════════════════════════════════════

// ignore: library_annotations
@Tags(['integration']) // antes de los imports: patrón de package:test para tags de archivo
import 'package:anime_tracker/models/anime.dart';
import 'package:anime_tracker/services/matching_service.dart';
import 'package:anime_tracker/services/scraper_service.dart';
import 'package:flutter_test/flutter_test.dart';

/// Corre el matching e imprime todo lo necesario para inspección visual.
///
/// Devuelve el resultado para las verificaciones mínimas del llamador.
/// Falla con mensaje claro si el servicio no está corriendo.
Future<ResultadoMatching> _inspeccionar(
  String etiqueta,
  Anime anime,
  ScraperService scraper,
) async {
  late final ResultadoMatching resultado;
  try {
    resultado = await encontrarFuenteParaAnime(anime, scraper: scraper);
  } on ScraperNoDisponibleException catch (e) {
    fail(
      'scraper-service no disponible en ${ScraperService.baseUrl} '
      '(¿corriste `npm start` en scraper-service?). Detalle: $e',
    );
  }

  final titulosAnime = [
    if (anime.tituloRomaji != null && anime.tituloRomaji!.trim().isNotEmpty)
      anime.tituloRomaji!,
    if (anime.tituloEnglish != null && anime.tituloEnglish!.trim().isNotEmpty)
      anime.tituloEnglish!,
  ];

  print('--- $etiqueta ---');
  print('anime: ${titulosAnime.join(' / ')}');
  print('candidatos: ${resultado.candidatos.length}');
  for (final c in resultado.candidatos) {
    var mejor = 0.0;
    for (final t in titulosAnime) {
      final s = similitudTitulos(c.titulo, t);
      if (s > mejor) mejor = s;
    }
    print(
      '  - "${c.titulo}" | slug=${c.slug} | '
      'score=${mejor.toStringAsFixed(3)} | url=${c.url}',
    );
  }
  if (resultado.tieneAutomatica) {
    print(
      'AUTOMATICO: "${resultado.automatica!.titulo}" -> '
      '${resultado.automatica!.url}',
    );
  } else {
    print('SIN automatico (elegir manual o vacio)');
  }
  return resultado;
}

void main() {
  late ScraperService scraper;

  setUp(() {
    // Servicio real, base por defecto http://localhost:3000.
    scraper = ScraperService();
  });

  tearDown(() => scraper.dispose());

  test(
    '1. "One Piece" encuentra fuente (inspección visual)',
    () async {
      const anime = Anime(id: 21, tituloRomaji: 'One Piece');
      final resultado = await _inspeccionar('One Piece', anime, scraper);

      // End-to-end mínimo: la búsqueda real debe traer algo.
      expect(
        resultado.candidatos,
        isNotEmpty,
        reason: 'El scraper-service debería devolver al menos un resultado.',
      );
      // Intencionalmente SIN assert estricto sobre automatica: si es null
      // se revisa en consola (ver AVISO).
      if (!resultado.tieneAutomatica) {
        print('AVISO: se esperaba coincidencia automática y fue null.');
      }
    },
    timeout: const Timeout(Duration(seconds: 60)),
  );

  test(
    '2. "Re:Zero ... 4th Season" encuentra fuente (inspección visual)',
    () async {
      const anime = Anime(
        id: 999002,
        tituloRomaji: 'Re:Zero kara Hajimeru Isekai Seikatsu 4th Season',
      );
      final resultado = await _inspeccionar('Re:Zero 4th Season', anime, scraper);

      expect(
        resultado.candidatos,
        isNotEmpty,
        reason: 'El scraper-service debería devolver al menos un resultado.',
      );
      if (!resultado.tieneAutomatica) {
        print('AVISO: se esperaba coincidencia automática y fue null.');
      }
    },
    timeout: const Timeout(Duration(seconds: 60)),
  );

  test(
    '3. Anime inventado no matchea (automatica null)',
    () async {
      const anime = Anime(
        id: 999999,
        tituloRomaji: 'Anime Que No Existe XYZ123',
      );
      final resultado = await _inspeccionar(
        'Anime inventado',
        anime,
        scraper,
      );

      expect(
        resultado.automatica,
        isNull,
        reason: 'Un título inventado no debe producir match automático.',
      );
    },
    timeout: const Timeout(Duration(seconds: 60)),
  );
}

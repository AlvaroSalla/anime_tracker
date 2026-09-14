import 'package:anime_tracker/models/anime.dart';
import 'package:anime_tracker/models/entrada_biblioteca.dart';
import 'package:anime_tracker/models/fuente_video.dart';
import 'package:anime_tracker/screens/detalle_anime_screen.dart';
import 'package:anime_tracker/screens/reproductor_screen.dart';
import 'package:anime_tracker/services/anilist_service.dart';
import 'package:anime_tracker/services/matching_service.dart';
import 'package:anime_tracker/services/scraper_service.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fake_biblioteca_repository.dart';

/// No hay WebView en `flutter test`: la fábrica que lanza fuerza el
/// marcador neutro y deja testear el flujo A-C, los chips y el progreso.
Never _sinWebView() => throw UnsupportedError('sin webview en tests');

const _anime = Anime(id: 21, tituloRomaji: 'One Piece', episodios: 12);

const _fuente = ResultadoBusquedaFuente(
  titulo: 'One Piece',
  slug: 'one-piece',
  url: 'https://animeflv.or.at/anime/one-piece/',
);

/// Fake de [ScraperService]: solo memoria, sin red.
class FakeScraper extends ScraperService {
  final List<EpisodioFuente> episodios;
  final List<ServidorVideo> servidores;

  FakeScraper({this.episodios = const [], this.servidores = const []});

  @override
  Future<List<ResultadoBusquedaFuente>> buscar(
    String query, {
    String sitio = 'animeflv',
  }) async => [];

  @override
  Future<List<EpisodioFuente>> obtenerEpisodios(
    String slug, {
    String sitio = 'animeflv',
  }) async => episodios;

  @override
  Future<List<ServidorVideo>> obtenerVideo(
    String urlEpisodio, {
    String sitio = 'animeflv',
  }) async => servidores;
}

Future<ResultadoMatching> _auto(
  Anime anime, {
  ScraperService? scraper,
  String sitio = 'animeflv',
}) async => const ResultadoMatching(
  automatica: _fuente,
  candidatos: [_fuente],
);

Future<ResultadoMatching> _vacio(
  Anime anime, {
  ScraperService? scraper,
  String sitio = 'animeflv',
}) async => const ResultadoMatching(automatica: null, candidatos: []);

Future<void> _pumpReproductor(
  WidgetTester tester, {
  required FakeScraper scraper,
  required FakeBibliotecaRepository repo,
  int episodio = 3,
  BuscarFuenteFn buscarFuente = _auto,
  // En false no espera settle: para cuando queda un diálogo abierto
  // con el spinner de fondo (el spinner nunca "termina" de animar).
  bool settled = true,
}) async {
  await tester.pumpWidget(
    MaterialApp(
      home: ReproductorScreen(
        anime: _anime,
        episodio: episodio,
        scraper: scraper,
        repository: repo,
        buscarFuente: buscarFuente,
        crearControlador: _sinWebView,
      ),
    ),
  );
  if (settled) {
    await tester.pumpAndSettle();
  } else {
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));
  }
}

void main() {
  testWidgets('flujo automático muestra chips de servidor', (tester) async {
    await _pumpReproductor(
      tester,
      scraper: FakeScraper(
        episodios: const [EpisodioFuente(numero: 3, url: 'https://ep/3')],
        servidores: const [
          ServidorVideo(servidor: 'Server A', url: 'https://a'),
          ServidorVideo(servidor: 'Server B', url: 'https://b'),
        ],
      ),
      repo: FakeBibliotecaRepository(),
    );

    expect(find.text('One Piece · Episodio 3'), findsOneWidget);
    expect(find.text('Server A'), findsOneWidget);
    expect(find.text('Server B'), findsOneWidget);
    // Sin WebView en tests: marcador neutro en lugar del player.
    expect(find.byKey(const ValueKey('visor-marcador')), findsOneWidget);

    // Cambiar de servidor no rompe.
    await tester.tap(find.text('Server B'));
    await tester.pumpAndSettle();
    expect(find.text('Server B'), findsOneWidget);
  });

  testWidgets('un solo servidor no muestra chips', (tester) async {
    await _pumpReproductor(
      tester,
      scraper: FakeScraper(
        episodios: const [EpisodioFuente(numero: 3, url: 'https://ep/3')],
        servidores: const [ServidorVideo(servidor: 'default', url: 'https://a')],
      ),
      repo: FakeBibliotecaRepository(),
    );

    expect(find.text('default'), findsNothing);
    expect(find.byKey(const ValueKey('visor-marcador')), findsOneWidget);
  });

  testWidgets('sin candidatos muestra error con volver', (tester) async {
    await _pumpReproductor(
      tester,
      scraper: FakeScraper(),
      repo: FakeBibliotecaRepository(),
      buscarFuente: _vacio,
    );

    expect(
      find.text('No se encontró este anime en las fuentes disponibles'),
      findsOneWidget,
    );
    await tester.tap(find.text('Volver'));
    await tester.pumpAndSettle();
    expect(find.byType(ReproductorScreen), findsNothing);
  });

  testWidgets('episodio faltante en la fuente muestra error', (tester) async {
    await _pumpReproductor(
      tester,
      scraper: FakeScraper(
        episodios: const [EpisodioFuente(numero: 1, url: 'https://ep/1')],
      ),
      repo: FakeBibliotecaRepository(),
      episodio: 3,
    );

    expect(
      find.text('Episodio no disponible en esta fuente'),
      findsOneWidget,
    );
  });

  testWidgets('candidatos ambiguos abren diálogo y eligen', (tester) async {
    const otra = ResultadoBusquedaFuente(
      titulo: 'One Piece Especial',
      slug: 'one-piece-especial',
      url: 'https://animeflv.or.at/anime/one-piece-especial/',
    );
    Future<ResultadoMatching> ambiguo(
      Anime anime, {
      ScraperService? scraper,
      String sitio = 'animeflv',
    }) async => const ResultadoMatching(
      automatica: null,
      candidatos: [_fuente, otra],
    );

    await _pumpReproductor(
      tester,
      scraper: FakeScraper(
        episodios: const [EpisodioFuente(numero: 3, url: 'https://ep/3')],
        servidores: const [ServidorVideo(servidor: 'default', url: 'https://a')],
      ),
      repo: FakeBibliotecaRepository(),
      buscarFuente: ambiguo,
      settled: false,
    );

    expect(find.text('¿Cuál es el anime correcto?'), findsOneWidget);
    await tester.tap(find.text('One Piece Especial'));
    await tester.pumpAndSettle();

    // Eligió la segunda: el flujo siguió hasta el visor.
    expect(
      find.text('¿Cuál es el anime correcto?'),
      findsNothing,
    );
    expect(find.byKey(const ValueKey('visor-marcador')), findsOneWidget);
  });

  testWidgets('al volver actualiza el progreso si se avanzó', (tester) async {
    final repo = FakeBibliotecaRepository([
      EntradaBiblioteca(
        animeId: _anime.id,
        tituloAnime: _anime.tituloDisplay,
        episodioActual: 2,
      ),
    ]);
    await _pumpReproductor(
      tester,
      scraper: FakeScraper(),
      repo: repo,
      episodio: 5,
      buscarFuente: _vacio,
    );

    // En error hay botón Volver (el BackButton del AppBar solo existe
    // cuando la pantalla fue pusheada sobre otra ruta).
    await tester.tap(find.text('Volver'));
    await tester.pumpAndSettle();

    expect(find.byType(ReproductorScreen), findsNothing);
    expect((await repo.obtenerPorAnimeId(_anime.id))!.episodioActual, 5);
  });

  testWidgets('al volver no baja el progreso ya guardado', (tester) async {
    final repo = FakeBibliotecaRepository([
      EntradaBiblioteca(
        animeId: _anime.id,
        tituloAnime: _anime.tituloDisplay,
        episodioActual: 7,
      ),
    ]);
    await _pumpReproductor(
      tester,
      scraper: FakeScraper(),
      repo: repo,
      episodio: 5,
      buscarFuente: _vacio,
    );

    await tester.tap(find.text('Volver'));
    await tester.pumpAndSettle();

    expect((await repo.obtenerPorAnimeId(_anime.id))!.episodioActual, 7);
  });

  testWidgets('si no está en biblioteca no agrega nada al salir',
      (tester) async {
    final repo = FakeBibliotecaRepository();
    await _pumpReproductor(
      tester,
      scraper: FakeScraper(),
      repo: repo,
      episodio: 5,
      buscarFuente: _vacio,
    );

    await tester.tap(find.text('Volver'));
    await tester.pumpAndSettle();

    expect(await repo.obtenerPorAnimeId(_anime.id), isNull);
    expect(await repo.obtenerTodas(), isEmpty);
  });

  testWidgets('el back del sistema también actualiza el progreso',
      (tester) async {
    final repo = FakeBibliotecaRepository([
      EntradaBiblioteca(
        animeId: _anime.id,
        tituloAnime: _anime.tituloDisplay,
        episodioActual: 2,
      ),
    ]);
    await _pumpReproductor(
      tester,
      scraper: FakeScraper(),
      repo: repo,
      episodio: 5,
      buscarFuente: _vacio,
    );

    // Back del sistema: pasa por el PopScope -> mismo _volver().
    await tester.binding.handlePopRoute();
    await tester.pumpAndSettle();

    expect(find.byType(ReproductorScreen), findsNothing);
    expect((await repo.obtenerPorAnimeId(_anime.id))!.episodioActual, 5);
  });

  testWidgets('el play del detalle navega al reproductor', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: DetalleAnimeScreen(
          animeId: _anime.id,
          animeInicial: _anime,
          service: _FakeAnilist(),
          repository: FakeBibliotecaRepository(),
          scraper: FakeScraper(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    // El fake no devuelve candidatos: el reproductor muestra ese error,
    // lo que igual prueba que se navegó en vez de marcar directo.
    await tester.tap(find.widgetWithIcon(IconButton, Icons.play_arrow).first);
    await tester.pumpAndSettle();

    expect(find.byType(ReproductorScreen), findsOneWidget);
    expect(
      find.text('No se encontró este anime en las fuentes disponibles'),
      findsOneWidget,
    );
  });
}

class _FakeAnilist extends AnilistService {
  @override
  Future<Anime> obtenerDetalle(int id) async => _anime;

  @override
  Future<List<Anime>> obtenerTrending({int pagina = 1}) async => [];

  @override
  Future<List<Anime>> buscarAnime(String query) async => [];
}

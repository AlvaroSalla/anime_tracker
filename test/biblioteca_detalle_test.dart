import 'package:anime_tracker/models/anime.dart';
import 'package:anime_tracker/models/entrada_biblioteca.dart';
import 'package:anime_tracker/screens/biblioteca_screen.dart';
import 'package:anime_tracker/screens/detalle_anime_screen.dart';
import 'package:anime_tracker/services/anilist_service.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fake_biblioteca_repository.dart';

/// Prueba de los dos bugs con un finalizado y un en emisión:
/// - ambos aparecen en "Mi biblioteca" tras agregarlos;
/// - la lista de episodios del finalizado usa el total y la del
///   en emisión se infiere desde `nextAiringEpisode - 1`.
///
/// Todo en memoria (fake de repositorio + fake de servicio): el sqlite
/// real no avanza en `testWidgets`. La cobertura del sqlite real queda
/// en `biblioteca_repository_test.dart`.
class _FakeDetalleService extends AnilistService {
  final Map<int, Anime> detalles;

  _FakeDetalleService(this.detalles);

  @override
  Future<Anime> obtenerDetalle(int id) async {
    final anime = detalles[id];
    if (anime == null) {
      throw AnilistException('No se encontró el anime con id $id.');
    }
    return anime;
  }

  @override
  Future<List<Anime>> obtenerTrending({int pagina = 1}) async => [];

  @override
  Future<List<Anime>> buscarAnime(String query) async => [];
}

void main() {
  const finalizado = Anime(
    id: 21,
    tituloRomaji: 'Anime Finalizado',
    episodios: 12,
    status: 'FINISHED',
  );
  const enEmision = Anime(
    id: 22,
    tituloRomaji: 'Anime En Emision',
    episodios: null,
    proximoEpisodio: 8,
    status: 'RELEASING',
  );

  _FakeDetalleService servicio() => _FakeDetalleService(
        {finalizado.id: finalizado, enEmision.id: enEmision},
      );

  FakeBibliotecaRepository repoConDos() => FakeBibliotecaRepository([
        EntradaBiblioteca(
          animeId: finalizado.id,
          tituloAnime: finalizado.tituloDisplay,
          episodiosTotales: finalizado.episodios,
        ),
        EntradaBiblioteca(
          animeId: enEmision.id,
          tituloAnime: enEmision.tituloDisplay,
          episodiosTotales: enEmision.episodios,
          episodioActual: 5,
        ),
      ]);

  testWidgets(
      'agregar finalizado y en emisión: ambos aparecen en Mi biblioteca',
      (WidgetTester tester) async {
    final repo = repoConDos();

    // Confirma que el dato llegó a la base (diagnóstico del BUG 1).
    final todas = await repo.obtenerTodas();
    expect(todas.length, 2);

    await tester.pumpWidget(
      MaterialApp(
        home: BibliotecaScreen(repository: repo, service: servicio()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Mi biblioteca (2)'), findsOneWidget);
    expect(find.text('Anime Finalizado'), findsOneWidget);
    expect(find.text('Anime En Emision'), findsOneWidget);
    // Progreso: total conocido vs. total desconocido.
    expect(find.text('0/12 eps  ·  Pendiente'), findsOneWidget);
    expect(find.text('5 vistos  ·  Pendiente'), findsOneWidget);
  });

  testWidgets('tocar una fila abre el detalle y al volver sigue la lista',
      (WidgetTester tester) async {
    final repo = repoConDos();
    await tester.pumpWidget(
      MaterialApp(
        home: BibliotecaScreen(repository: repo, service: servicio()),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Anime En Emision'));
    await tester.pumpAndSettle();

    // Detalle del en emisión: 7 emitidos (nextAiring 8 - 1).
    // La lista es lazy: scrollear hasta el último esperado.
    await tester.scrollUntilVisible(find.text('Episodio 7'), 400);
    await tester.pumpAndSettle();
    expect(find.text('Episodio 7'), findsOneWidget);
    expect(find.text('Episodio 8'), findsNothing);

    await tester.tap(find.byType(BackButton));
    await tester.pumpAndSettle();

    // Al volver se recargó y la lista sigue completa.
    expect(find.text('Mi biblioteca (2)'), findsOneWidget);
  });

  testWidgets('detalle finalizado lista 12 episodios', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: DetalleAnimeScreen(
          animeId: finalizado.id,
          animeInicial: finalizado,
          service: servicio(),
          repository: FakeBibliotecaRepository(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Episodio 1'), findsOneWidget);
    expect(find.text('0/12 vistos'), findsOneWidget);
    // La lista es lazy: scrollear hasta el último.
    await tester.scrollUntilVisible(find.text('Episodio 12'), 400);
    await tester.pumpAndSettle();
    expect(find.text('Episodio 12'), findsOneWidget);
  });

  testWidgets('detalle en emisión lista hasta nextAiring - 1', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: DetalleAnimeScreen(
          animeId: enEmision.id,
          animeInicial: enEmision,
          service: servicio(),
          repository: FakeBibliotecaRepository(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    // Emitidos: 7. El 8 todavía no salió.
    // (Headers primero: tras scrollear quedan fuera de vista.)
    expect(
      find.text('En emisión: se listan los episodios ya emitidos.'),
      findsOneWidget,
    );
    // Dos veces: estado "En emisión" + total "En emisión" (sin "?").
    expect(find.text('En emisión'), findsNWidgets(2));
    // La lista es lazy: scrollear hasta el último esperado; si el 8
    // existiera, se construiría al quedar adyacente.
    await tester.scrollUntilVisible(find.text('Episodio 7'), 400);
    await tester.pumpAndSettle();
    expect(find.text('Episodio 7'), findsOneWidget);
    expect(find.text('Episodio 8'), findsNothing);
  });

  testWidgets('agregar en emisión desde el detalle persiste el progreso',
      (tester) async {
    final repo = FakeBibliotecaRepository();
    await tester.pumpWidget(
      MaterialApp(
        home: DetalleAnimeScreen(
          animeId: enEmision.id,
          animeInicial: enEmision,
          service: servicio(),
          repository: repo,
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Agregar a mi biblioteca'));
    await tester.pumpAndSettle();

    expect(find.text('En mi biblioteca'), findsOneWidget);

    final entrada = await repo.obtenerPorAnimeId(enEmision.id);
    expect(entrada, isNotNull);
    expect(entrada!.episodiosTotales, isNull);
  });
}

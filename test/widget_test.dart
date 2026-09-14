import 'package:anime_tracker/models/anime.dart';
import 'package:anime_tracker/screens/app_shell.dart';
import 'package:anime_tracker/services/anilist_service.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fake_biblioteca_repository.dart';

/// Fake sin red: devuelve datos fijos. Las portadas son `null` a
/// propósito para que el test no intente cargar imágenes de red.
class _FakeAnilistService extends AnilistService {
  @override
  Future<List<Anime>> obtenerTrending({int pagina = 1}) async {
    return const [
      Anime(
        id: 21,
        tituloRomaji: 'One Piece',
        averageScore: 87,
        generos: ['Action', 'Adventure'],
        seasonYear: 1999,
      ),
      Anime(
        id: 20,
        tituloRomaji: 'Naruto',
        averageScore: 79,
        generos: ['Action'],
        seasonYear: 2002,
      ),
    ];
  }

  @override
  Future<List<Anime>> buscarAnime(String query) async => [];
}

void main() {
  // Biblioteca en memoria: el sqlite real no avanza en testWidgets
  // (zona fake-async). Ver fake_biblioteca_repository.dart.
  FakeBibliotecaRepository repoVacio() => FakeBibliotecaRepository();

  testWidgets('AppShell muestra rail + inicio con trending',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: AppShell(
          service: _FakeAnilistService(),
          repository: repoVacio(),
        ),
      ),
    );
    // Deja que el Future de trending complete y reconstruya.
    await tester.pump();

    // Items del rail.
    expect(find.text('Inicio'), findsOneWidget);
    expect(find.text('Mi biblioteca'), findsOneWidget);
    expect(find.text('Configuración'), findsOneWidget);

    // Secciones de inicio con datos del fake.
    expect(find.text('Recomendado para vos'), findsOneWidget);
    expect(find.text('Más vistos según AniList'), findsOneWidget);
    expect(find.text('One Piece'), findsNWidgets(2)); // card + tile
    expect(find.text('Naruto'), findsNWidgets(2));

    // Sin spinner una vez cargado.
    expect(find.byType(CircularProgressIndicator), findsNothing);
  });

  testWidgets('Navegar a una sección placeholder muestra "Próximamente"',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: AppShell(
          service: _FakeAnilistService(),
          repository: repoVacio(),
        ),
      ),
    );
    await tester.pump();

    await tester.tap(find.text('Favoritos'));
    await tester.pump();

    expect(find.text('Próximamente'), findsOneWidget);
  });

  testWidgets('Mi biblioteca muestra lo guardado en sqlite',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: AppShell(
          service: _FakeAnilistService(),
          repository: repoVacio(),
        ),
      ),
    );
    await tester.pump();

    await tester.tap(find.text('Mi biblioteca'));
    await tester.pumpAndSettle();

    // Pantalla real (ya no placeholder): arranca vacía.
    expect(find.text('Tu biblioteca está vacía'), findsOneWidget);
  });
}

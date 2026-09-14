import 'package:anime_tracker/data/biblioteca_repository.dart';
import 'package:anime_tracker/data/database_helper.dart';
import 'package:anime_tracker/models/entrada_biblioteca.dart';
import 'package:flutter_test/flutter_test.dart';
// Incluye la API de sqflite (inMemoryDatabasePath, databaseFactory)
// más el backend FFI necesario en desktop.
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

/// Tests del repositorio contra una base SQLite **en memoria**.
///
/// No toca la base real de la app: cada test abre una BD volátil
/// (`inMemoryDatabasePath`) que se descarta al cerrar la conexión.
/// Requiere `sqflite_common_ffi` porque `flutter test` corre en la
/// máquina host (Windows/Linux), donde el plugin `sqflite` clásico
/// no tiene implementación.
void main() {
  late BibliotecaRepository repo;

  setUpAll(() {
    // Backend SQLite para tests en desktop.
    sqfliteFfiInit();
    databaseFactory = databaseFactoryFfi;
  });

  setUp(() {
    // BD fresca en memoria para cada test.
    DatabaseHelper.instance.setOverridePath(inMemoryDatabasePath);
    repo = BibliotecaRepository();
  });

  tearDown(() async {
    await DatabaseHelper.instance.close();
  });

  EntradaBiblioteca entradaPrueba() => EntradaBiblioteca(
        animeId: 21,
        tituloAnime: 'One Piece',
        imagenPortada: 'https://example.com/one-piece.jpg',
        estado: EstadoBiblioteca.viendo,
        episodioActual: 3,
        episodiosTotales: 1100,
        calificacionPersonal: 9,
      );

  test('agregar → existe y se puede leer', () async {
    expect(await repo.existeEnBiblioteca(21), isFalse);
    expect(await repo.obtenerPorAnimeId(21), isNull);

    await repo.agregar(entradaPrueba());

    expect(await repo.existeEnBiblioteca(21), isTrue);

    final leida = await repo.obtenerPorAnimeId(21);
    expect(leida, isNotNull);
    expect(leida!.animeId, 21);
    expect(leida.tituloAnime, 'One Piece');
    expect(leida.imagenPortada, 'https://example.com/one-piece.jpg');
    expect(leida.estado, EstadoBiblioteca.viendo);
    expect(leida.episodioActual, 3);
    expect(leida.episodiosTotales, 1100);
    expect(leida.calificacionPersonal, 9);
  });

  test('actualizar → persiste progreso, estado y fecha', () async {
    await repo.agregar(entradaPrueba());
    final antes = (await repo.obtenerPorAnimeId(21))!;

    await repo.actualizar(
      antes.copyWith(
        episodioActual: 4,
        estado: EstadoBiblioteca.completado,
        calificacionPersonal: () => 10,
      ),
    );

    final despues = (await repo.obtenerPorAnimeId(21))!;
    expect(despues.episodioActual, 4);
    expect(despues.estado, EstadoBiblioteca.completado);
    expect(despues.calificacionPersonal, 10);
    // fechaActualizado se refresca al actualizar.
    expect(
      despues.fechaActualizado.isAfter(antes.fechaActualizado) ||
          despues.fechaActualizado.isAtSameMomentAs(antes.fechaActualizado),
      isTrue,
    );
  });

  test('obtenerTodas y obtenerPorEstado filtran bien', () async {
    await repo.agregar(entradaPrueba());
    await repo.agregar(
      EntradaBiblioteca(
        animeId: 20,
        tituloAnime: 'Naruto',
        estado: EstadoBiblioteca.pendiente,
      ),
    );

    expect((await repo.obtenerTodas()).length, 2);

    final viendo = await repo.obtenerPorEstado(EstadoBiblioteca.viendo);
    expect(viendo.length, 1);
    expect(viendo.first.animeId, 21);

    final pendientes =
        await repo.obtenerPorEstado(EstadoBiblioteca.pendiente);
    expect(pendientes.length, 1);
    expect(pendientes.first.animeId, 20);

    final completados =
        await repo.obtenerPorEstado(EstadoBiblioteca.completado);
    expect(completados, isEmpty);
  });

  test('eliminar → ya no existe ni se puede leer', () async {
    await repo.agregar(entradaPrueba());
    expect(await repo.existeEnBiblioteca(21), isTrue);

    await repo.eliminar(21);

    expect(await repo.existeEnBiblioteca(21), isFalse);
    expect(await repo.obtenerPorAnimeId(21), isNull);
    expect(await repo.obtenerTodas(), isEmpty);
  });
}

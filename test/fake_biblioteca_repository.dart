import 'package:anime_tracker/data/biblioteca_repository.dart';
import 'package:anime_tracker/models/entrada_biblioteca.dart';
import 'package:flutter/foundation.dart';

/// Fake en memoria de [BibliotecaRepository] para widget tests.
///
/// El sqlite real (sqflite FFI) no avanza dentro de `testWidgets`:
/// corre en zona fake-async y a partir de la segunda operación el
/// `await` nunca vuelve. Este fake usa un Map con Futures inmediatos,
/// que sí completan con `pump()`. La cobertura del sqlite real queda
/// en `biblioteca_repository_test.dart` (tests puros, zona real).
class FakeBibliotecaRepository extends BibliotecaRepository {
  final Map<int, EntradaBiblioteca> _datos = {};

  FakeBibliotecaRepository([
    Iterable<EntradaBiblioteca> iniciales = const [],
  ]) : super() {
    for (final entrada in iniciales) {
      _datos[entrada.animeId] = entrada;
    }
  }

  @override
  Future<void> agregar(EntradaBiblioteca entrada) async {
    _datos[entrada.animeId] = entrada;
    debugPrint(
      '[Biblioteca-fake] agregar OK: animeId=${entrada.animeId} '
      'titulo="${entrada.tituloAnime}"',
    );
  }

  @override
  Future<void> actualizar(EntradaBiblioteca entrada) async {
    _datos[entrada.animeId] = entrada.copyWith(
      fechaActualizado: DateTime.now(),
    );
  }

  @override
  Future<void> eliminar(int animeId) async {
    _datos.remove(animeId);
  }

  @override
  Future<List<EntradaBiblioteca>> obtenerTodas() async {
    final lista = _datos.values.toList()
      ..sort(
        (a, b) => b.fechaActualizado.compareTo(a.fechaActualizado),
      );
    debugPrint(
      '[Biblioteca-fake] obtenerTodas() → ${lista.length} entradas: '
      '${lista.map((e) => e.animeId).toList()}',
    );
    return lista;
  }

  @override
  Future<List<EntradaBiblioteca>> obtenerPorEstado(
    EstadoBiblioteca estado,
  ) async {
    return (await obtenerTodas())
        .where((e) => e.estado == estado)
        .toList();
  }

  @override
  Future<EntradaBiblioteca?> obtenerPorAnimeId(int animeId) async {
    return _datos[animeId];
  }

  @override
  Future<bool> existeEnBiblioteca(int animeId) async {
    return _datos.containsKey(animeId);
  }
}

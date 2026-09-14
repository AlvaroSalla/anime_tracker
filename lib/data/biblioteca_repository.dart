import 'package:sqflite/sqflite.dart';

import '../models/entrada_biblioteca.dart';
import 'database_helper.dart';

/// Capa de acceso a la tabla `biblioteca`.
///
/// Toda la SQL vive acá; la UI y los servicios hablan con este
/// repositorio, nunca con [DatabaseHelper] directamente.
class BibliotecaRepository {
  final DatabaseHelper _dbHelper;

  /// [dbHelper] es inyectable para tests (por defecto el singleton).
  BibliotecaRepository({DatabaseHelper? dbHelper})
      : _dbHelper = dbHelper ?? DatabaseHelper.instance;

  /// Agrega una entrada. Si el [animeId] ya existe, lo reemplaza
  /// (re-agregar equivale a actualizar).
  Future<void> agregar(EntradaBiblioteca entrada) async {
    final db = await _dbHelper.database;
    await db.insert(
      DatabaseHelper.tablaBiblioteca,
      entrada.toMap(),
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  /// Actualiza una entrada existente y refresca [fechaActualizado]
  /// al momento de la escritura.
  Future<void> actualizar(EntradaBiblioteca entrada) async {
    final db = await _dbHelper.database;
    final conFecha = entrada.copyWith(
      fechaActualizado: DateTime.now(),
    );
    await db.update(
      DatabaseHelper.tablaBiblioteca,
      conFecha.toMap(),
      where: 'animeId = ?',
      whereArgs: [entrada.animeId],
    );
  }

  /// Elimina la entrada de [animeId]. No falla si no existía.
  Future<void> eliminar(int animeId) async {
    final db = await _dbHelper.database;
    await db.delete(
      DatabaseHelper.tablaBiblioteca,
      where: 'animeId = ?',
      whereArgs: [animeId],
    );
  }

  /// Todas las entradas, las más recientemente actualizadas primero.
  Future<List<EntradaBiblioteca>> obtenerTodas() async {
    final db = await _dbHelper.database;
    final rows = await db.query(
      DatabaseHelper.tablaBiblioteca,
      orderBy: 'fechaActualizado DESC',
    );
    return rows.map(EntradaBiblioteca.fromMap).toList();
  }

  /// Entradas filtradas por [estado], más recientes primero.
  Future<List<EntradaBiblioteca>> obtenerPorEstado(
    EstadoBiblioteca estado,
  ) async {
    final db = await _dbHelper.database;
    final rows = await db.query(
      DatabaseHelper.tablaBiblioteca,
      where: 'estado = ?',
      whereArgs: [estado.name],
      orderBy: 'fechaActualizado DESC',
    );
    return rows.map(EntradaBiblioteca.fromMap).toList();
  }

  /// Una entrada por su [animeId], o `null` si no está en la biblioteca.
  Future<EntradaBiblioteca?> obtenerPorAnimeId(int animeId) async {
    final db = await _dbHelper.database;
    final rows = await db.query(
      DatabaseHelper.tablaBiblioteca,
      where: 'animeId = ?',
      whereArgs: [animeId],
      limit: 1,
    );
    if (rows.isEmpty) return null;
    return EntradaBiblioteca.fromMap(rows.first);
  }

  /// `true` si [animeId] ya está guardado en la biblioteca.
  Future<bool> existeEnBiblioteca(int animeId) async {
    final db = await _dbHelper.database;
    final rows = await db.query(
      DatabaseHelper.tablaBiblioteca,
      columns: const ['animeId'],
      where: 'animeId = ?',
      whereArgs: [animeId],
      limit: 1,
    );
    return rows.isNotEmpty;
  }
}

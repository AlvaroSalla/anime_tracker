import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:path/path.dart' as p;
// Re-exporta toda la API de sqflite (Database, openDatabase,
// getDatabasesPath, databaseFactory) + init FFI para desktop.
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

/// Acceso singleton a la base de datos SQLite de la app.
///
/// - En Android/iOS/macOS usa el plugin `sqflite` clásico.
/// - En Windows/Linux (desktop) activa `sqflite_common_ffi`, porque el
///   plugin clásico no tiene implementación en esas plataformas. Esto
///   también es lo que permite correr los tests con `flutter test`
///   en esta máquina.
/// - La ruta sale de `getDatabasesPath()` (directorio de datos de la
///   app), por eso no hizo falta agregar `path_provider`.
class DatabaseHelper {
  DatabaseHelper._internal();

  /// Instancia única compartida por toda la app.
  static final DatabaseHelper instance = DatabaseHelper._internal();

  /// Permite `DatabaseHelper()` como alias del singleton.
  factory DatabaseHelper() => instance;

  static const String dbName = 'anime_tracker.db';

  /// Subir este número cada vez que cambie el esquema y agregar la
  /// migración correspondiente en [_onUpgrade].
  static const int dbVersion = 1;

  static const String tablaBiblioteca = 'biblioteca';

  Database? _database;

  /// Ruta alternativa (solo tests). Si se fija, se usa en lugar de
  /// `<app-data>/anime_tracker.db`. Para BD en memoria pasar
  /// `inMemoryDatabasePath` de `package:sqflite/sqflite.dart`.
  String? _overridePath;

  bool _ffiReady = false;

  /// Fija una ruta alternativa para tests. Debe llamarse antes del
  /// primer acceso a [database].
  @visibleForTesting
  void setOverridePath(String path) {
    _overridePath = path;
  }

  /// Cierra la conexión y olvida la instancia cacheada. En tests se
  /// usa en `tearDown` para aislar cada caso.
  Future<void> close() async {
    await _database?.close();
    _database = null;
    _overridePath = null;
  }

  /// Conexión abierta (perezosa): se crea en el primer acceso y se
  /// reutiliza después.
  Future<Database> get database async {
    if (_database != null) return _database!;
    _database = await _open();
    return _database!;
  }

  Future<Database> _open() async {
    _ensureFfiIfNeeded();
    final String path;
    if (_overridePath != null) {
      path = _overridePath!;
    } else {
      final dir = await getDatabasesPath();
      path = p.join(dir, dbName);
    }
    return openDatabase(
      path,
      version: dbVersion,
      onCreate: _onCreate,
      onUpgrade: _onUpgrade,
    );
  }

  /// En desktop el plugin `sqflite` no tiene implementación nativa,
  /// así que se delega en la implementación FFI (sqlite3 embebido).
  void _ensureFfiIfNeeded() {
    if (_ffiReady) return;
    if (Platform.isWindows || Platform.isLinux) {
      sqfliteFfiInit();
      databaseFactory = databaseFactoryFfi;
    }
    _ffiReady = true;
  }

  Future<void> _onCreate(Database db, int version) async {
    await db.execute('''
CREATE TABLE $tablaBiblioteca(
  animeId INTEGER PRIMARY KEY,
  tituloAnime TEXT NOT NULL,
  imagenPortada TEXT,
  estado TEXT NOT NULL,
  episodioActual INTEGER NOT NULL DEFAULT 0,
  episodiosTotales INTEGER,
  fechaAgregado INTEGER NOT NULL,
  fechaActualizado INTEGER NOT NULL,
  calificacionPersonal INTEGER
)
''');
  }

  /// Migraciones incrementales entre versiones.
  ///
  /// Al cambiar el esquema: subir [dbVersion] y agregar un bloque
  /// `if (oldVersion < N)` por cada versión nueva. Ejemplo futuro:
  /// ```dart
  /// if (oldVersion < 2) {
  ///   await db.execute(
  ///     'ALTER TABLE $tablaBiblioteca ADD COLUMN notas TEXT',
  ///   );
  /// }
  /// ```
  Future<void> _onUpgrade(Database db, int oldVersion, int newVersion) async {
    // v1 es la versión inicial: no hay nada que migrar todavía.
    // Los futuros cambios se agregan aquí como `if (oldVersion < N)`.
  }
}

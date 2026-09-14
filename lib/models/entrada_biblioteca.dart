/// Estado de una entrada dentro de la biblioteca del usuario.
enum EstadoBiblioteca {
  /// El usuario la está viendo actualmente.
  viendo,

  /// El usuario la terminó.
  completado,

  /// En la lista para ver más adelante.
  pendiente,

  /// El usuario la dejó.
  abandonado,
}

/// Una fila de la tabla `biblioteca`: el seguimiento local de un anime.
///
/// Guarda una copia mínima de los datos de AniList ([tituloAnime] e
/// [imagenPortada]) para poder mostrar la biblioteca sin consultar
/// la API en cada apertura. La referencia al anime remoto es [animeId]
/// (el `Media.id` de AniList) y funciona como clave primaria.
class EntradaBiblioteca {
  /// ID del anime en AniList. Clave primaria en SQLite.
  final int animeId;

  /// Título guardado al momento de agregar (para uso offline).
  final String tituloAnime;

  /// URL de portada guardada al momento de agregar. Nullable: el
  /// anime puede no traer imagen.
  final String? imagenPortada;

  /// En qué lista está la entrada.
  final EstadoBiblioteca estado;

  /// Episodio por el que va el usuario.
  final int episodioActual;

  /// Total de episodios conocidos. `null` si se desconoce
  /// (anime en emisión o sin dato en AniList).
  final int? episodiosTotales;

  /// Cuándo se agregó a la biblioteca.
  final DateTime fechaAgregado;

  /// Última modificación (progreso, estado o calificación).
  final DateTime fechaActualizado;

  /// Puntaje personal del usuario, de 1 a 10. `null` = sin puntuar.
  final int? calificacionPersonal;

  EntradaBiblioteca({
    required this.animeId,
    required this.tituloAnime,
    this.imagenPortada,
    this.estado = EstadoBiblioteca.pendiente,
    this.episodioActual = 0,
    this.episodiosTotales,
    DateTime? fechaAgregado,
    DateTime? fechaActualizado,
    this.calificacionPersonal,
  })  : assert(animeId > 0, 'animeId debe ser mayor a 0.'),
        assert(episodioActual >= 0, 'episodioActual no puede ser negativo.'),
        assert(
          calificacionPersonal == null ||
              (calificacionPersonal >= 1 && calificacionPersonal <= 10),
          'calificacionPersonal debe estar entre 1 y 10.',
        ),
        fechaAgregado = fechaAgregado ?? DateTime.now(),
        fechaActualizado = fechaActualizado ?? DateTime.now();

  /// Copia con campos modificados. Útil para actualizar progreso,
  /// estado o calificación sin reconstruir el objeto a mano.
  EntradaBiblioteca copyWith({
    String? tituloAnime,
    String? Function()? imagenPortada,
    EstadoBiblioteca? estado,
    int? episodioActual,
    int? Function()? episodiosTotales,
    DateTime? fechaAgregado,
    DateTime? fechaActualizado,
    int? Function()? calificacionPersonal,
  }) {
    return EntradaBiblioteca(
      animeId: animeId,
      tituloAnime: tituloAnime ?? this.tituloAnime,
      imagenPortada:
          imagenPortada != null ? imagenPortada() : this.imagenPortada,
      estado: estado ?? this.estado,
      episodioActual: episodioActual ?? this.episodioActual,
      episodiosTotales: episodiosTotales != null
          ? episodiosTotales()
          : this.episodiosTotales,
      fechaAgregado: fechaAgregado ?? this.fechaAgregado,
      fechaActualizado: fechaActualizado ?? this.fechaActualizado,
      calificacionPersonal: calificacionPersonal != null
          ? calificacionPersonal()
          : this.calificacionPersonal,
    );
  }

  /// Convierte a mapa para SQLite. Las fechas se guardan como
  /// milisegundos desde epoch (`INTEGER`) y el estado por su nombre.
  Map<String, dynamic> toMap() {
    return {
      'animeId': animeId,
      'tituloAnime': tituloAnime,
      'imagenPortada': imagenPortada,
      'estado': estado.name,
      'episodioActual': episodioActual,
      'episodiosTotales': episodiosTotales,
      'fechaAgregado': fechaAgregado.millisecondsSinceEpoch,
      'fechaActualizado': fechaActualizado.millisecondsSinceEpoch,
      'calificacionPersonal': calificacionPersonal,
    };
  }

  /// Reconstruye desde una fila de SQLite.
  factory EntradaBiblioteca.fromMap(Map<String, dynamic> map) {
    return EntradaBiblioteca(
      animeId: (map['animeId'] as num).toInt(),
      tituloAnime: map['tituloAnime'] as String,
      imagenPortada: map['imagenPortada'] as String?,
      estado: EstadoBiblioteca.values.byName(map['estado'] as String),
      episodioActual: (map['episodioActual'] as num).toInt(),
      episodiosTotales: (map['episodiosTotales'] as num?)?.toInt(),
      fechaAgregado:
          DateTime.fromMillisecondsSinceEpoch((map['fechaAgregado'] as num).toInt()),
      fechaActualizado: DateTime.fromMillisecondsSinceEpoch(
          (map['fechaActualizado'] as num).toInt()),
      calificacionPersonal: (map['calificacionPersonal'] as num?)?.toInt(),
    );
  }

  @override
  String toString() =>
      'EntradaBiblioteca(animeId: $animeId, titulo: $tituloAnime, '
      'estado: ${estado.name}, progreso: $episodioActual/${episodiosTotales ?? '?'})';
}

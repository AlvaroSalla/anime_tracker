/// Modelo de dominio para un anime obtenido desde AniList.
///
/// Mapea el objeto `Media(type: ANIME)` de la API GraphQL de AniList.
/// Ver: https://docs.anilist.co/guide/graphql/
class Anime {
  /// ID numérico de AniList (`Media.id`).
  final int id;

  /// Título en romaji. AniList casi siempre lo devuelve, pero lo
  /// dejamos nullable por seguridad ante respuestas incompletas.
  final String? tituloRomaji;

  /// Título en inglés. Suele ser `null` para muchos animes.
  final String? tituloEnglish;

  /// URL de la portada (`coverImage.large`). Nullable: algunos
  /// resultados pueden no traer imagen.
  final String? coverImageUrl;

  /// URL del banner panorámico (`bannerImage`). Frecuentemente `null`.
  final String? bannerImageUrl;

  /// Sinopsis (`description`). AniList la devuelve con tags HTML
  /// (`<br>`, `<i>`, etc.). Se guarda tal cual; la UI decide si
  /// sanearla antes de mostrarla.
  final String? descripcion;

  /// Lista de géneros (`genres`). Por defecto lista vacía, nunca null.
  final List<String> generos;

  /// Puntaje promedio 0-100 (`averageScore`). Nullable.
  final int? averageScore;

  /// Cantidad de episodios (`episodes`). `null` si aún se desconoce
  /// (anime en emisión o no estrenado). Siempre nullable: nunca asumir
  /// que viene un número.
  final int? episodios;

  /// Próximo episodio a emitirse (`nextAiringEpisode.episode`).
  /// Solo tiene valor en animes en emisión; permite inferir cuántos
  /// episodios ya salieron cuando [episodios] (total final) es `null`.
  final int? proximoEpisodio;

  /// Estado (`status`): p. ej. `FINISHED`, `RELEASING`, `NOT_YET_RELEASED`,
  /// `CANCELLED`, `HIATUS`.
  final String? status;

  /// Temporada (`season`): `WINTER`, `SPRING`, `SUMMER`, `FALL`.
  final String? season;

  /// Año de la temporada (`seasonYear`).
  final int? seasonYear;

  const Anime({
    required this.id,
    this.tituloRomaji,
    this.tituloEnglish,
    this.coverImageUrl,
    this.bannerImageUrl,
    this.descripcion,
    this.generos = const [],
    this.averageScore,
    this.episodios,
    this.proximoEpisodio,
    this.status,
    this.season,
    this.seasonYear,
  });

  /// Título más presentable: prefiere romaji, cae a inglés, y como
  /// último recurso muestra `Anime #id`.
  String get tituloDisplay {
    if (tituloRomaji != null && tituloRomaji!.isNotEmpty) {
      return tituloRomaji!;
    }
    if (tituloEnglish != null && tituloEnglish!.isNotEmpty) {
      return tituloEnglish!;
    }
    return 'Anime #$id';
  }

  /// Cantidad de episodios que se pueden listar hoy.
  ///
  /// - Si se conoce el total ([episodios]), se usa ese.
  /// - Si el total es `null` (en emisión), se infiere desde
  ///   [proximoEpisodio]: ya salieron `proximoEpisodio - 1`.
  /// - Nunca baja de [episodioActual] (lo ya visto siempre se lista).
  /// - Devuelve 0 cuando no hay ningún episodio confirmado todavía.
  int episodiosVisibles(int episodioActual) {
    if (episodios != null && episodios! > 0) return episodios!;
    final emitidos = (proximoEpisodio ?? 1) - 1;
    if (emitidos <= 0) return episodioActual > 0 ? episodioActual : 0;
    return emitidos > episodioActual ? emitidos : episodioActual;
  }

  /// Parsea un objeto `Media` de AniList tal cual viene en el JSON.
  ///
  /// Ejemplo de fragmento esperado:
  /// ```json
  /// {
  ///   "id": 21,
  ///   "title": {"romaji": "One Piece", "english": "One Piece"},
  ///   "coverImage": {"large": "https://..."},
  ///   "bannerImage": "https://...",
  ///   "description": "...",
  ///   "genres": ["Action", "Adventure"],
  ///   "averageScore": 87,
  ///   "episodes": 1100,
  ///   "nextAiringEpisode": {"episode": 1101},
  ///   "status": "RELEASING",
  ///   "season": "FALL",
  ///   "seasonYear": 1999
  /// }
  /// ```
  factory Anime.fromJson(Map<String, dynamic> json) {
    final title = json['title'] as Map<String, dynamic>?;
    final coverImage = json['coverImage'] as Map<String, dynamic>?;
    final genresJson = json['genres'] as List<dynamic>?;
    final nextAiring = json['nextAiringEpisode'] as Map<String, dynamic>?;

    return Anime(
      id: (json['id'] as num).toInt(),
      tituloRomaji: title?['romaji'] as String?,
      tituloEnglish: title?['english'] as String?,
      coverImageUrl: coverImage?['large'] as String?,
      bannerImageUrl: json['bannerImage'] as String?,
      descripcion: json['description'] as String?,
      generos: genresJson == null
          ? const []
          : genresJson.whereType<String>().toList(),
      averageScore: (json['averageScore'] as num?)?.toInt(),
      episodios: (json['episodes'] as num?)?.toInt(),
      proximoEpisodio: (nextAiring?['episode'] as num?)?.toInt(),
      status: json['status'] as String?,
      season: json['season'] as String?,
      seasonYear: (json['seasonYear'] as num?)?.toInt(),
    );
  }

  @override
  String toString() => 'Anime(id: $id, titulo: $tituloDisplay)';
}

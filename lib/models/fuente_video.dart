/// Modelos para las respuestas del scraper-service (Node, AnimeFLV).
///
/// El servicio expone:
/// - GET `/buscar?sitio=animeflv&q=...` -> `{resultados: [{titulo, slug, url, imagen}]}`
/// - GET `/episodios?sitio=animeflv&slug=...` -> `{episodios: [{numero, url}]}`
/// - GET `/video?sitio=animeflv&url=...` -> `{servidores: [{servidor, url}]}`
/// Ver `scraper-service/` (fuera de este repo Flutter).
library;

/// Un anime encontrado en la fuente externa (AnimeFLV).
class ResultadoBusquedaFuente {
  /// Título tal cual lo devuelve la fuente (ej. "One Piece").
  final String titulo;

  /// Slug dentro de la fuente (ej. "one-piece"). Nullable: la fuente
  /// podría no proveerlo; en ese caso se deriva de [url] si se puede.
  final String? slug;

  /// URL completa de la página del anime en la fuente.
  final String url;

  /// URL de portada en la fuente. Nullable.
  final String? imagen;

  const ResultadoBusquedaFuente({
    required this.titulo,
    required this.url,
    this.slug,
    this.imagen,
  });

  /// Parsea un item de `resultados` del GET /buscar.
  factory ResultadoBusquedaFuente.fromJson(Map<String, dynamic> json) {
    return ResultadoBusquedaFuente(
      titulo: json['titulo'] as String,
      slug: json['slug'] as String?,
      url: json['url'] as String,
      imagen: json['imagen'] as String?,
    );
  }

  @override
  String toString() =>
      'ResultadoBusquedaFuente(titulo: $titulo, slug: $slug, url: $url)';
}

/// Un episodio disponible en la fuente externa.
class EpisodioFuente {
  /// Número de episodio (1-based).
  final int numero;

  /// URL de la página del episodio. Nullable: la fuente podría listar
  /// solo números sin link directo.
  final String? url;

  const EpisodioFuente({required this.numero, this.url});

  /// Parsea un item de `episodios` del GET /episodios.
  factory EpisodioFuente.fromJson(Map<String, dynamic> json) {
    return EpisodioFuente(
      numero: (json['numero'] as num).toInt(),
      url: json['url'] as String?,
    );
  }

  @override
  String toString() => 'EpisodioFuente(numero: $numero, url: $url)';
}

/// Un servidor de video ya resuelto (URL de embed/video directa).
class ServidorVideo {
  /// Nombre del servidor según la fuente (ej. "default", "Servidor 1").
  final String servidor;

  /// URL directa del video/embed.
  final String url;

  const ServidorVideo({required this.servidor, required this.url});

  /// Parsea un item de `servidores` del GET /video.
  factory ServidorVideo.fromJson(Map<String, dynamic> json) {
    return ServidorVideo(
      servidor: json['servidor'] as String,
      url: json['url'] as String,
    );
  }

  @override
  String toString() => 'ServidorVideo(servidor: $servidor, url: $url)';
}

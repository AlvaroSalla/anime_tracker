import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../models/fuente_video.dart';

/// El scraper-service no está corriendo o no hay conexión con él.
///
/// Distinto de [ScraperException]: esta es falla de red/conexión local,
/// la otra es un error con mensaje real devuelto por el servicio (400/502).
class ScraperNoDisponibleException implements Exception {
  final String message;
  const ScraperNoDisponibleException(this.message);

  @override
  String toString() => 'ScraperNoDisponibleException: $message';
}

/// Error devuelto por el scraper-service (400/502, con su mensaje real).
///
/// Ejemplos: sitio no soportado, parámetro faltante, o la estructura del
/// sitio cambió ("No se encontró el reproductor...").
class ScraperException implements Exception {
  final String message;
  final int? statusCode;
  const ScraperException(this.message, [this.statusCode]);

  @override
  String toString() => 'ScraperException: $message';
}

/// Cliente para el scraper-service local (Node + Express).
///
/// Endpoints (ya probados contra el sitio real):
/// - GET `/buscar?sitio=animeflv&q=...`
/// - GET `/episodios?sitio=animeflv&slug=...`
/// - GET `/video?sitio=animeflv&url=...`
class ScraperService {
  /// URL base del servicio. Cambiar acá cuando se despliegue fuera de
  /// localhost (ej. a la URL del servidor real).
  static const String baseUrl = 'http://localhost:3000';

  final http.Client _client;
  final String _baseUrl;

  /// [client] inyectable para tests con mock. [baseUrl] inyectable para
  /// apuntar a otro entorno sin tocar la constante.
  ScraperService({http.Client? client, String? baseUrl})
    : _client = client ?? http.Client(),
      _baseUrl = baseUrl ?? ScraperService.baseUrl;

  /// Busca animes en la fuente por nombre.
  ///
  /// Devuelve lista vacía si no hay resultados (no es error).
  /// Lanza [ScraperNoDisponibleException] si el servicio no corre y
  /// [ScraperException] con el mensaje real ante 400/502 del servicio.
  Future<List<ResultadoBusquedaFuente>> buscar(
    String query, {
    String sitio = 'animeflv',
  }) async {
    final trimmed = query.trim();
    if (trimmed.isEmpty) {
      throw const ScraperException('La búsqueda no puede estar vacía.');
    }
    final body = await _getJson('/buscar', {
      'sitio': sitio,
      'q': trimmed,
    });
    final resultados = body['resultados'] as List<dynamic>? ?? const [];
    return resultados
        .whereType<Map<String, dynamic>>()
        .map(ResultadoBusquedaFuente.fromJson)
        .toList();
  }

  /// Lista los episodios disponibles para [slug] (o URL del anime).
  Future<List<EpisodioFuente>> obtenerEpisodios(
    String slug, {
    String sitio = 'animeflv',
  }) async {
    final trimmed = slug.trim();
    if (trimmed.isEmpty) {
      throw const ScraperException('Falta el slug del anime.');
    }
    final body = await _getJson('/episodios', {
      'sitio': sitio,
      'slug': trimmed,
    });
    final episodios = body['episodios'] as List<dynamic>? ?? const [];
    return episodios
        .whereType<Map<String, dynamic>>()
        .map(EpisodioFuente.fromJson)
        .toList();
  }

  /// Resuelve los servidores de video para la página del episodio.
  ///
  /// [urlEpisodio] es la URL completa (la que viene en [EpisodioFuente.url]).
  Future<List<ServidorVideo>> obtenerVideo(
    String urlEpisodio, {
    String sitio = 'animeflv',
  }) async {
    final trimmed = urlEpisodio.trim();
    if (trimmed.isEmpty) {
      throw const ScraperException('Falta la URL del episodio.');
    }
    final body = await _getJson('/video', {
      'sitio': sitio,
      'url': trimmed,
    });
    final servidores = body['servidores'] as List<dynamic>? ?? const [];
    return servidores
        .whereType<Map<String, dynamic>>()
        .map(ServidorVideo.fromJson)
        .toList();
  }

  /// Cierra el cliente HTTP subyacente.
  void dispose() => _client.close();

  /// GET + parseo JSON con manejo de errores diferenciado.
  ///
  /// - Falla de red/conexión -> [ScraperNoDisponibleException].
  /// - Status != 200 -> [ScraperException] con el `error` real del servicio.
  Future<Map<String, dynamic>> _getJson(
    String path,
    Map<String, String> query,
  ) async {
    final uri = Uri.parse('$_baseUrl$path').replace(queryParameters: query);
    http.Response response;
    try {
      response = await _client.get(
        uri,
        headers: {HttpHeaders.acceptHeader: 'application/json'},
      );
    } on SocketException {
      throw ScraperNoDisponibleException(
        'No se pudo conectar con el scraper-service en $_baseUrl. '
        'Verificá que esté corriendo (npm start).',
      );
    } on http.ClientException catch (e) {
      throw ScraperNoDisponibleException(
        'No se pudo conectar con el scraper-service: ${e.message}',
      );
    } catch (e) {
      throw ScraperNoDisponibleException(
        'Error inesperado al contactar el scraper-service: $e',
      );
    }

    if (response.statusCode != 200) {
      throw ScraperException(
        _mensajeErrorReal(response) ??
            'El scraper-service respondió con HTTP ${response.statusCode}.',
        response.statusCode,
      );
    }

    try {
      return jsonDecode(response.body) as Map<String, dynamic>;
    } catch (_) {
      throw const ScraperException(
        'Respuesta inválida del scraper-service (no es JSON).',
      );
    }
  }

  /// Extrae el `error` real del cuerpo (el servicio siempre responde
  /// `{error: "..."}` en fallos). `null` si no hay mensaje parseable.
  String? _mensajeErrorReal(http.Response response) {
    try {
      final decoded = jsonDecode(response.body);
      if (decoded is Map<String, dynamic>) {
        final error = decoded['error'];
        if (error is String && error.isNotEmpty) return error;
      }
    } catch (_) {
      // Cuerpo no-JSON: se usa el mensaje genérico con el status.
    }
    return null;
  }
}

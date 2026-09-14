import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../models/anime.dart';

/// Excepción de dominio para errores de la API de AniList.
///
/// Se lanza cuando la respuesta HTTP no es 200, cuando el JSON trae
/// un campo `errors`, o cuando hay un fallo de red/parseo.
class AnilistException implements Exception {
  final String message;
  const AnilistException(this.message);

  @override
  String toString() => 'AnilistException: $message';
}

/// Cliente liviano para la API GraphQL pública de AniList.
///
/// Endpoint: https://graphql.anilist.co
/// Solo lectura, sin API key. Peticiones POST con `query` + `variables`.
class AnilistService {
  static const String _endpoint = 'https://graphql.anilist.co';

  final http.Client _client;

  /// Permite inyectar un [http.Client] (útil para tests con mock).
  AnilistService({http.Client? client}) : _client = client ?? http.Client();

  // -----------------------------------------------------------------
  // Queries GraphQL (una por operación)
  // -----------------------------------------------------------------

  /// Búsqueda de anime por nombre.
  static const String _buscarAnimeQuery = r'''
query ($search: String) {
  Page(perPage: 10) {
    media(search: $search, type: ANIME) {
      id
      title { romaji english }
      coverImage { large }
      bannerImage
      description
      genres
      averageScore
      episodes
      status
      season
      seasonYear
    }
  }
}
''';

  /// Detalle completo de un anime por ID.
  static const String _detalleAnimeQuery = r'''
query ($id: Int) {
  Media(id: $id, type: ANIME) {
    id
    title { romaji english }
    coverImage { large }
    bannerImage
    description
    genres
    averageScore
    episodes
    status
    season
    seasonYear
  }
}
''';

  /// Lista de trending (para la sección "más vistos").
  static const String _trendingQuery = r'''
query ($page: Int, $perPage: Int) {
  Page(page: $page, perPage: $perPage) {
    media(sort: TRENDING_DESC, type: ANIME) {
      id
      title { romaji english }
      coverImage { large }
      bannerImage
      description
      genres
      averageScore
      episodes
      status
      season
      seasonYear
    }
  }
}
''';

  // -----------------------------------------------------------------
  // Métodos públicos
  // -----------------------------------------------------------------

  /// Busca animes por [query] (nombre).
  ///
  /// Devuelve hasta 10 resultados. Lanza [AnilistException] si la
  /// búsqueda está vacía, hay error de red o la API responde con error.
  Future<List<Anime>> buscarAnime(String query) async {
    final trimmed = query.trim();
    if (trimmed.isEmpty) {
      throw const AnilistException(
        'La búsqueda no puede estar vacía.',
      );
    }

    final body = await _postGraphql(
      _buscarAnimeQuery,
      variables: {'search': trimmed},
    );

    final page = body['data']?['Page'] as Map<String, dynamic>?;
    final media = page?['media'] as List<dynamic>? ?? const [];
    return media
        .whereType<Map<String, dynamic>>()
        .map(Anime.fromJson)
        .toList();
  }

  /// Trae el detalle completo de un anime por su [id] de AniList.
  ///
  /// Lanza [AnilistException] si el ID es inválido, el anime no existe
  /// o la API responde con error.
  Future<Anime> obtenerDetalle(int id) async {
    if (id <= 0) {
      throw const AnilistException('ID de anime inválido.');
    }

    final body = await _postGraphql(
      _detalleAnimeQuery,
      variables: {'id': id},
    );

    final media = body['data']?['Media'] as Map<String, dynamic>?;
    if (media == null) {
      throw AnilistException('No se encontró el anime con id $id.');
    }
    return Anime.fromJson(media);
  }

  /// Trae la lista de trending para la sección "más vistos".
  ///
  /// [pagina] empieza en 1. Trae 10 items por página por defecto.
  Future<List<Anime>> obtenerTrending({int pagina = 1}) async {
    if (pagina < 1) {
      throw const AnilistException('La página debe ser mayor a 0.');
    }

    final body = await _postGraphql(
      _trendingQuery,
      variables: {'page': pagina, 'perPage': 10},
    );

    final page = body['data']?['Page'] as Map<String, dynamic>?;
    final media = page?['media'] as List<dynamic>? ?? const [];
    return media
        .whereType<Map<String, dynamic>>()
        .map(Anime.fromJson)
        .toList();
  }

  /// Cierra el cliente HTTP subyacente.
  void dispose() => _client.close();

  // -----------------------------------------------------------------
  // Helpers privados
  // -----------------------------------------------------------------

  /// Hace el POST GraphQL y devuelve el `data` decodificado.
  ///
  /// Lanza [AnilistException] con mensaje legible si:
  /// - no hay conexión / falla de red,
  /// - el status HTTP no es 200,
  /// - el cuerpo no es JSON válido,
  /// - el JSON trae campo `errors` (error de GraphQL, p. ej. rate limit).
  Future<Map<String, dynamic>> _postGraphql(
    String query, {
    required Map<String, dynamic> variables,
  }) async {
    http.Response response;
    try {
      response = await _client.post(
        Uri.parse(_endpoint),
        headers: {
          HttpHeaders.contentTypeHeader: 'application/json',
          HttpHeaders.acceptHeader: 'application/json',
        },
        body: jsonEncode({'query': query, 'variables': variables}),
      );
    } on SocketException {
      throw const AnilistException(
        'Sin conexión a internet. Revisá tu red e intentá de nuevo.',
      );
    } on http.ClientException catch (e) {
      throw AnilistException('Error de red: ${e.message}');
    } catch (e) {
      throw AnilistException('Error inesperado de red: $e');
    }

    if (response.statusCode != 200) {
      throw AnilistException(
        'AniList respondió con HTTP ${response.statusCode}. '
        'Intentá de nuevo más tarde.',
      );
    }

    late final Map<String, dynamic> decoded;
    try {
      decoded = jsonDecode(response.body) as Map<String, dynamic>;
    } catch (_) {
      throw const AnilistException(
        'Respuesta inválida de AniList (no es JSON).',
      );
    }

    // AniList puede responder 200 con campo "errors" (GraphQL errors,
    // p. ej. "Too Many Requests" por rate limit).
    if (decoded['errors'] != null) {
      final errors = decoded['errors'] as List<dynamic>;
      final first = errors.isNotEmpty
          ? (errors.first as Map<String, dynamic>)['message']
          : null;
      throw AnilistException(
        'Error de AniList: ${first ?? 'error desconocido'}.',
      );
    }

    return decoded;
  }
}

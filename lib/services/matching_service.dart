import '../models/anime.dart';
import '../models/fuente_video.dart';
import 'scraper_service.dart';

/// Umbral para considerar una coincidencia como "fuerte".
///
/// La igualdad normalizada da 1.0 y la contención 0.9, así que 0.85
/// acepta ambas más diferencias mínimas (typos/puntuación), pero no
/// títulos apenas parecidos.
const double umbralCoincidenciaFuerte = 0.85;

/// Resultado del intento de matcheo automático.
///
/// - [automatica] es no-null solo si hay UNA coincidencia clara.
/// - [candidatos] es la lista completa para elección manual cuando
///   [automatica] es null (ambigua o vacía). Nunca asumir si hay duda.
class ResultadoMatching {
  final ResultadoBusquedaFuente? automatica;
  final List<ResultadoBusquedaFuente> candidatos;

  const ResultadoMatching({
    required this.automatica,
    required this.candidatos,
  });

  /// `true` si se encontró una coincidencia clara.
  bool get tieneAutomatica => automatica != null;
}

/// Normaliza un título para comparar: minúsculas, sin tildes,
/// sin puntuación, espacios colapsados.
///
/// Ej: "Re:Zero — kara Hajimeru!" -> "rezero kara hajimeru".
String normalizarTitulo(String titulo) {
  var s = titulo.toLowerCase();
  const conTilde = 'áéíóúüñàèìòùâêîôûäëïöç';
  const sinTilde = 'aeiouunaeiouaeiouaeioc';
  for (var i = 0; i < conTilde.length; i++) {
    s = s.replaceAll(conTilde[i], sinTilde[i]);
  }
  s = s.replaceAll(RegExp(r'[^a-z0-9 ]'), ' ');
  return s.replaceAll(RegExp(r'\s+'), ' ').trim();
}

/// Similitud 0..1 entre dos títulos ya pensando en normalizados.
///
/// - 1.0 si son iguales normalizados.
/// - 0.9 si uno contiene al otro (ej. con sufijo "4th season").
/// - Si no, 1 - (levenshtein / largo máximo).
double similitudTitulos(String a, String b) {
  final na = normalizarTitulo(a);
  final nb = normalizarTitulo(b);
  if (na.isEmpty || nb.isEmpty) return 0.0;
  if (na == nb) return 1.0;
  if (na.contains(nb) || nb.contains(na)) return 0.9;
  final dist = distanciaLevenshtein(na, nb);
  final maxLen = na.length > nb.length ? na.length : nb.length;
  return 1.0 - dist / maxLen;
}

/// Distancia de edición (Levenshtein) entre dos strings.
int distanciaLevenshtein(String s, String t) {
  if (s == t) return 0;
  if (s.isEmpty) return t.length;
  if (t.isEmpty) return s.length;
  var anterior = List<int>.generate(t.length + 1, (j) => j);
  for (var i = 1; i <= s.length; i++) {
    var actual = <int>[i];
    for (var j = 1; j <= t.length; j++) {
      final costo = s.codeUnitAt(i - 1) == t.codeUnitAt(j - 1) ? 0 : 1;
      actual.add(
        [actual[j - 1] + 1, anterior[j] + 1, anterior[j - 1] + costo].reduce(
          (a, b) => a < b ? a : b,
        ),
      );
    }
    anterior = actual;
  }
  return anterior[t.length];
}

/// Puntaje de un resultado de la fuente contra los títulos del [anime]
/// (máximo entre romaji e inglés disponibles).
double _puntajeContraAnime(ResultadoBusquedaFuente r, Anime anime) {
  var mejor = 0.0;
  for (final t in [anime.tituloRomaji, anime.tituloEnglish]) {
    if (t == null || t.trim().isEmpty) continue;
    final sim = similitudTitulos(r.titulo, t);
    if (sim > mejor) mejor = sim;
  }
  return mejor;
}

/// Intenta encontrar automáticamente la fuente correcta para [anime].
///
/// Estrategia:
/// 1. Busca con el romaji; si no hay resultados, reintenta con el inglés.
/// 2. Puntúa cada candidato contra romaji/inglés.
/// 3. Si hay EXACTAMENTE UNA coincidencia fuerte (>= [umbralCoincidenciaFuerte]),
///    la devuelve en [ResultadoMatching.automatica].
/// 4. Si hay varias fuertes (ambiguo) o ninguna, [automatica] es null y
///    [candidatos] trae la lista completa para elección manual.
///
/// No pega a la red en tests si se inyecta un [scraper] fake.
Future<ResultadoMatching> encontrarFuenteParaAnime(
  Anime anime, {
  ScraperService? scraper,
  String sitio = 'animeflv',
}) async {
  final propio = scraper == null;
  final servicio = scraper ?? ScraperService();
  try {
    final titulos = <String>[];
    if (anime.tituloRomaji != null && anime.tituloRomaji!.trim().isNotEmpty) {
      titulos.add(anime.tituloRomaji!.trim());
    }
    final ingles = anime.tituloEnglish?.trim() ?? '';
    if (ingles.isNotEmpty &&
        (titulos.isEmpty || normalizarTitulo(ingles) != normalizarTitulo(titulos.first))) {
      titulos.add(ingles);
    }
    if (titulos.isEmpty) {
      return const ResultadoMatching(automatica: null, candidatos: []);
    }

    var candidatos = await servicio.buscar(titulos.first, sitio: sitio);
    if (candidatos.isEmpty && titulos.length > 1) {
      candidatos = await servicio.buscar(titulos[1], sitio: sitio);
    }
    if (candidatos.isEmpty) {
      return const ResultadoMatching(automatica: null, candidatos: []);
    }

    ResultadoBusquedaFuente? mejor;
    var mejorPuntaje = 0.0;
    var fuertes = 0;
    for (final c in candidatos) {
      final p = _puntajeContraAnime(c, anime);
      if (p >= umbralCoincidenciaFuerte) fuertes++;
      if (p > mejorPuntaje) {
        mejorPuntaje = p;
        mejor = c;
      }
    }
    if (fuertes == 1 && mejorPuntaje >= umbralCoincidenciaFuerte) {
      return ResultadoMatching(automatica: mejor, candidatos: candidatos);
    }
    return ResultadoMatching(automatica: null, candidatos: candidatos);
  } finally {
    if (propio) servicio.dispose();
  }
}

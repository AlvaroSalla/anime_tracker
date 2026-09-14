import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';

import '../data/biblioteca_repository.dart';
import '../models/anime.dart';
import '../models/fuente_video.dart';
import '../services/matching_service.dart';
import '../services/scraper_service.dart';
import '../widgets/anime_image.dart';

/// Firma inyectable del PASO A (para tests sin red).
typedef BuscarFuenteFn =
    Future<ResultadoMatching> Function(
      Anime anime, {
      ScraperService? scraper,
      String sitio,
    });

/// Fábrica del controlador del visor. En tests se inyecta una que lanza
/// (no hay WebView en `flutter test`); en producción crea el real.
WebViewController _crearControladorDefault() => WebViewController();

/// Pantalla del reproductor: resuelve la fuente del episodio y la muestra
/// en un [WebViewWidget] (los embeds son iframes de terceros, no siempre
/// video directo reproducible de forma nativa).
///
/// Flujo:
/// - A: [encontrarFuenteParaAnime] (diálogo si hay que elegir manual).
/// - B: [ScraperService.obtenerEpisodios] + match por número.
/// - C: [ScraperService.obtenerVideo] + chips si hay varios servidores.
/// - D: WebView a casi pantalla completa.
///
/// Al salir, si el episodio visto supera el `episodioActual` guardado en
/// la biblioteca, actualiza el progreso. Si el anime no está en la
/// biblioteca, no hace nada (no agrega sin que el usuario lo pida).
class ReproductorScreen extends StatefulWidget {
  /// Anime a reproducir (viene del detalle).
  final Anime anime;

  /// Número de episodio pedido (1-based).
  final int episodio;

  /// Inyectables para tests. Si no se pasan, el screen crea los propios.
  final ScraperService? scraper;
  final BibliotecaRepository? repository;

  /// PASO A inyectable (por defecto el matching real).
  final BuscarFuenteFn buscarFuente;

  /// Sitio de la fuente (hoy solo 'animeflv').
  final String sitio;

  /// Fábrica del controlador WebView (seam para tests).
  final WebViewController Function() crearControlador;

  const ReproductorScreen({
    super.key,
    required this.anime,
    required this.episodio,
    this.scraper,
    this.repository,
    this.buscarFuente = encontrarFuenteParaAnime,
    this.sitio = 'animeflv',
    this.crearControlador = _crearControladorDefault,
  });

  @override
  State<ReproductorScreen> createState() => _ReproductorScreenState();
}

enum _Fase { cargando, error, listo }

class _ReproductorScreenState extends State<ReproductorScreen> {
  late final ScraperService _scraper;
  late final bool _poseeScraper;
  late final BibliotecaRepository _repository;

  _Fase _fase = _Fase.cargando;
  String _mensajeCarga = 'Buscando fuente de video...';
  String _error = '';

  List<ServidorVideo> _servidores = const [];
  int _servidorElegido = 0;

  WebViewController? _controller;
  bool _errorWeb = false;
  String _errorWebDetalle = '';

  @override
  void initState() {
    super.initState();
    _poseeScraper = widget.scraper == null;
    _scraper = widget.scraper ?? ScraperService();
    _repository = widget.repository ?? BibliotecaRepository();
    _iniciar();
  }

  @override
  void dispose() {
    if (_poseeScraper) _scraper.dispose();
    super.dispose();
  }

  // -----------------------------------------------------------------
  // Flujo A -> B -> C
  // -----------------------------------------------------------------

  Future<void> _iniciar() async {
    // PASO A - Buscar fuente.
    _aCargando('Buscando fuente de video...');
    late final ResultadoMatching matching;
    try {
      matching = await widget.buscarFuente(
        widget.anime,
        scraper: _scraper,
        sitio: widget.sitio,
      );
    } on ScraperNoDisponibleException catch (e) {
      _aError(e.message);
      return;
    } on ScraperException catch (e) {
      _aError(e.message);
      return;
    } catch (e) {
      _aError('Error inesperado: $e');
      return;
    }
    if (!mounted) return;

    var fuente = matching.automatica;
    if (fuente == null) {
      if (matching.candidatos.isEmpty) {
        _aError('No se encontró este anime en las fuentes disponibles');
        return;
      }
      fuente = await _elegirFuente(matching.candidatos);
      if (!mounted) return;
      if (fuente == null) {
        _aError('No se eligió ninguna fuente');
        return;
      }
    }

    // PASO B - Obtener episodios de la fuente.
    _aCargando('Buscando episodio...');
    late final List<EpisodioFuente> episodios;
    try {
      episodios = await _scraper.obtenerEpisodios(
        fuente.slug ?? fuente.url,
        sitio: widget.sitio,
      );
    } on ScraperNoDisponibleException catch (e) {
      _aError(e.message);
      return;
    } on ScraperException catch (e) {
      _aError(e.message);
      return;
    } catch (e) {
      _aError('Error inesperado: $e');
      return;
    }
    if (!mounted) return;

    EpisodioFuente? coincidencia;
    for (final e in episodios) {
      if (e.numero == widget.episodio) {
        coincidencia = e;
        break;
      }
    }
    if (coincidencia == null || (coincidencia.url ?? '').isEmpty) {
      _aError('Episodio no disponible en esta fuente');
      return;
    }

    // PASO C - Resolver video.
    _aCargando('Cargando video...');
    late final List<ServidorVideo> servidores;
    try {
      servidores = await _scraper.obtenerVideo(
        coincidencia.url!,
        sitio: widget.sitio,
      );
    } on ScraperNoDisponibleException catch (e) {
      _aError(e.message);
      return;
    } on ScraperException catch (e) {
      _aError(e.message);
      return;
    } catch (e) {
      _aError('Error inesperado: $e');
      return;
    }
    if (!mounted) return;
    if (servidores.isEmpty) {
      _aError('No se pudo resolver el video en esta fuente');
      return;
    }

    _servidores = servidores;
    _cargarServidor(0);
  }

  void _aCargando(String mensaje) {
    if (!mounted) return;
    setState(() {
      _fase = _Fase.cargando;
      _mensajeCarga = mensaje;
    });
  }

  void _aError(String mensaje) {
    if (!mounted) return;
    setState(() {
      _fase = _Fase.error;
      _error = mensaje;
    });
  }

  /// Diálogo de elección manual cuando el matching no fue automático.
  /// Devuelve la fuente elegida o `null` si se canceló.
  Future<ResultadoBusquedaFuente?> _elegirFuente(
    List<ResultadoBusquedaFuente> candidatos,
  ) {
    return showDialog<ResultadoBusquedaFuente>(
      context: context,
      builder: (context) => SimpleDialog(
        title: const Text('¿Cuál es el anime correcto?'),
        children: [
          for (final c in candidatos)
            SimpleDialogOption(
              onPressed: () => Navigator.of(context).pop(c),
              child: Row(
                children: [
                  AnimeCoverImage(url: c.imagen, width: 40, height: 56),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      c.titulo,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  // -----------------------------------------------------------------
  // PASO D - Visor
  // -----------------------------------------------------------------

  /// Activa el servidor [i]. Si el WebView no se puede crear en este
  /// dispositivo (p. ej. desktop sin soporte), se muestra un marcador
  /// en vez de romper: los chips y el resto siguen funcionando.
  void _cargarServidor(int i) {
    if (!mounted) return;
    WebViewController? controller;
    try {
      controller =
          widget.crearControlador()
            ..setJavaScriptMode(JavaScriptMode.unrestricted)
            ..setNavigationDelegate(
              NavigationDelegate(
                onWebResourceError: (error) {
                  if (!mounted) return;
                  setState(() {
                    _errorWeb = true;
                    _errorWebDetalle = error.description;
                  });
                },
              ),
            )
            ..loadRequest(Uri.parse(_servidores[i].url));
    } catch (_) {
      controller = null;
    }
    setState(() {
      _servidorElegido = i;
      _controller = controller;
      _errorWeb = false;
      _errorWebDetalle = '';
      _fase = _Fase.listo;
    });
  }

  /// Al salir: si lo visto supera el progreso guardado, lo actualiza.
  /// Si el anime no está en biblioteca, no hace nada.
  Future<void> _volver() async {
    try {
      final entrada =
          await _repository.obtenerPorAnimeId(widget.anime.id);
      if (entrada != null && widget.episodio > entrada.episodioActual) {
        await _repository.actualizar(
          entrada.copyWith(episodioActual: widget.episodio),
        );
      }
    } catch (_) {
      // No bloquear la salida por un fallo de persistencia.
    }
    if (!mounted) return;
    Navigator.of(context).pop();
  }

  // -----------------------------------------------------------------
  // UI
  // -----------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    return PopScope(
      // El Pop (sistema o AppBar) pasa siempre por [_volver] para
      // actualizar el progreso antes de salir.
      canPop: false,
      onPopInvokedWithResult: (didPop, _) async {
        if (!didPop) await _volver();
      },
      child: Scaffold(
        appBar: AppBar(
          title: Text(
            '${widget.anime.tituloDisplay} · Episodio ${widget.episodio}',
          ),
        ),
        body: _buildBody(),
      ),
    );
  }

  Widget _buildBody() {
    switch (_fase) {
      case _Fase.cargando:
        return Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const CircularProgressIndicator(),
              const SizedBox(height: 16),
              Text(_mensajeCarga),
            ],
          ),
        );
      case _Fase.error:
        return Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.cloud_off_outlined, size: 48),
                const SizedBox(height: 12),
                Text(_error, textAlign: TextAlign.center),
                const SizedBox(height: 12),
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    FilledButton.icon(
                      onPressed: () {
                        _servidores = const [];
                        _controller = null;
                        _iniciar();
                      },
                      icon: const Icon(Icons.refresh),
                      label: const Text('Reintentar'),
                    ),
                    const SizedBox(width: 12),
                    OutlinedButton(
                      onPressed: _volver,
                      child: const Text('Volver'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        );
      case _Fase.listo:
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (_servidores.length > 1)
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
                child: Row(
                  children: [
                    for (var i = 0; i < _servidores.length; i++) ...[
                      if (i > 0) const SizedBox(width: 8),
                      ChoiceChip(
                        label: Text(_servidores[i].servidor),
                        selected: _servidorElegido == i,
                        onSelected: (sel) {
                          if (sel) _cargarServidor(i);
                        },
                      ),
                    ],
                  ],
                ),
              ),
            Expanded(child: _buildVisor()),
          ],
        );
    }
  }

  Widget _buildVisor() {
    final controller = _controller;
    if (controller == null) {
      // Sin WebView en este entorno: marcador neutro (tests, desktop
      // sin soporte). No es un error del flujo A-C.
      return const Center(
        key: ValueKey('visor-marcador'),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.ondemand_video, size: 64),
            SizedBox(height: 12),
            Text('Reproductor no disponible en este dispositivo'),
          ],
        ),
      );
    }
    return Stack(
      children: [
        WebViewWidget(controller: controller),
        if (_errorWeb)
          Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            child: Material(
              color: Theme.of(context).colorScheme.errorContainer,
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Row(
                  children: [
                    Expanded(
                      child: Text(
                        'El video falló al cargar'
                        '${_errorWebDetalle.isEmpty ? '' : ': $_errorWebDetalle'}',
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    TextButton(
                      onPressed: () => _cargarServidor(_servidorElegido),
                      child: const Text('Reintentar'),
                    ),
                  ],
                ),
              ),
            ),
          ),
      ],
    );
  }
}

import 'package:flutter/material.dart';

import '../data/biblioteca_repository.dart';
import '../models/anime.dart';
import '../models/entrada_biblioteca.dart';
import '../services/anilist_service.dart';
import '../services/scraper_service.dart';
import '../widgets/anime_image.dart';
import '../widgets/modal_agregar_biblioteca.dart';
import 'reproductor_screen.dart';

/// Pantalla de detalle de un anime.
///
/// Recibe el [animeId] (siempre) y opcionalmente el [animeInicial] cuando
/// ya lo tenemos de una lista (trending / búsqueda). En ese caso se muestra
/// directo sin otra petición a la API; si no hay inicial, se trae con
/// [AnilistService.obtenerDetalle].
///
/// Incluye:
/// - Header con portada, título, chips de género, sinopsis y fila de
///   score / episodios / estado.
/// - Botón "Agregar a mi biblioteca" / "En mi biblioteca" (con confirmación
///   para quitar) + botón de favorito al lado.
/// - Lista de episodios (1..total) con estado visual según el progreso
///   guardado en la biblioteca. El play abre el [ReproductorScreen];
///   al salir, el reproductor actualiza `episodioActual` si se avanzó.
class DetalleAnimeScreen extends StatefulWidget {
  /// ID de AniList del anime a mostrar.
  final int animeId;

  /// Objeto ya conocido (de una lista). Evita una petición extra.
  final Anime? animeInicial;

  /// Inyectables para tests. Si no se pasan, el screen crea los propios.
  final AnilistService? service;
  final BibliotecaRepository? repository;

  /// Cliente del scraper-service para el reproductor (inyectable en
  /// tests; si no se pasa, el reproductor crea el propio).
  final ScraperService? scraper;

  const DetalleAnimeScreen({
    super.key,
    required this.animeId,
    this.animeInicial,
    this.service,
    this.repository,
    this.scraper,
  });

  @override
  State<DetalleAnimeScreen> createState() => _DetalleAnimeScreenState();
}

class _DetalleAnimeScreenState extends State<DetalleAnimeScreen> {
  late final AnilistService _service;
  late final bool _poseeServicio;
  late final BibliotecaRepository _repository;

  Anime? _anime;
  bool _cargandoDetalle = false;
  String? _errorDetalle;

  EntradaBiblioteca? _entrada;
  bool _cargandoBiblioteca = true;
  bool _guardando = false;

  /// Estado visual del corazón. Todavía no se persiste en SQLite
  /// (no hay columna/tabla de favoritos): se resuelve en el módulo
  /// de Favoritos / Mi biblioteca real.
  bool _esFavorito = false;

  @override
  void initState() {
    super.initState();
    _poseeServicio = widget.service == null;
    _service = widget.service ?? AnilistService();
    _repository = widget.repository ?? BibliotecaRepository();

    if (widget.animeInicial != null) {
      _anime = widget.animeInicial;
      _cargandoDetalle = false;
    } else {
      _cargandoDetalle = true;
      _cargarDetalle();
    }
    _cargarBiblioteca();
  }

  @override
  void dispose() {
    if (_poseeServicio) _service.dispose();
    super.dispose();
  }

  Future<void> _cargarDetalle() async {
    setState(() {
      _cargandoDetalle = true;
      _errorDetalle = null;
    });
    try {
      final detalle = await _service.obtenerDetalle(widget.animeId);
      if (!mounted) return;
      setState(() {
        _anime = detalle;
        _cargandoDetalle = false;
      });
    } on AnilistException catch (e) {
      if (!mounted) return;
      setState(() {
        _errorDetalle = e.message;
        _cargandoDetalle = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _errorDetalle = 'Error inesperado: $e';
        _cargandoDetalle = false;
      });
    }
  }

  Future<void> _cargarBiblioteca() async {
    setState(() => _cargandoBiblioteca = true);
    try {
      final entrada =
          await _repository.obtenerPorAnimeId(widget.animeId);
      if (!mounted) return;
      setState(() {
        _entrada = entrada;
        _cargandoBiblioteca = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _cargandoBiblioteca = false);
    }
  }

  /// Abre el modal de biblioteca: agregar si no está, editar si ya está.
  ///
  /// Al confirmar con Guardar se persiste con [agregar] o [actualizar]
  /// según corresponda; Quitar elimina (ya confirmado en el modal).
  Future<void> _abrirModalBiblioteca() async {
    final anime = _anime;
    if (anime == null || _guardando) return;

    final esEdicion = _entrada != null;
    final resultado = await mostrarModalAgregarBiblioteca(
      context: context,
      anime: anime,
      entradaExistente: _entrada,
    );
    if (resultado == null || !mounted) return;

    switch (resultado) {
      case GuardarBiblioteca(:final entrada):
        await _guardarEntrada(entrada, esEdicion: esEdicion);
      case QuitarBiblioteca():
        await _quitarDeBiblioteca();
    }
  }

  /// Persiste [entrada] (agregar o actualizar) y refresca la pantalla
  /// para que el botón pase a "En mi biblioteca".
  Future<void> _guardarEntrada(
    EntradaBiblioteca entrada, {
    required bool esEdicion,
  }) async {
    setState(() => _guardando = true);
    try {
      if (esEdicion) {
        await _repository.actualizar(entrada);
      } else {
        await _repository.agregar(entrada);
      }
      final actualizada =
          await _repository.obtenerPorAnimeId(entrada.animeId);
      final todas = await _repository.obtenerTodas();
      debugPrint(
        '[Detalle] tras guardar animeId=${entrada.animeId}: '
        'obtenerTodas() → ${todas.length} entradas: '
        '${todas.map((e) => e.animeId).toList()}',
      );
      if (!mounted) return;
      setState(() => _entrada = actualizada);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            esEdicion
                ? 'Cambios guardados en tu biblioteca'
                : 'Agregado a tu biblioteca',
          ),
        ),
      );
    } finally {
      if (mounted) setState(() => _guardando = false);
    }
  }

  /// Quita el anime de la biblioteca (la confirmación ya se pidió en
  /// el modal antes de devolver [QuitarBiblioteca]).
  Future<void> _quitarDeBiblioteca() async {
    setState(() => _guardando = true);
    try {
      await _repository.eliminar(widget.animeId);
      if (!mounted) return;
      setState(() => _entrada = null);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Quitado de tu biblioteca')),
      );
    } finally {
      if (mounted) setState(() => _guardando = false);
    }
  }

  /// Abre el reproductor para el episodio [numero].
  ///
  /// Al volver se relee la biblioteca: el reproductor ya actualizó
  /// `episodioActual` si se avanzó (y solo si el anime está guardado).
  Future<void> _abrirReproductor(int numero) async {
    final anime = _anime;
    if (anime == null) return;
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => ReproductorScreen(
          anime: anime,
          episodio: numero,
          repository: _repository,
          scraper: widget.scraper,
        ),
      ),
    );
    if (!mounted) return;
    await _cargarBiblioteca();
  }

  // -----------------------------------------------------------------
  // Helpers de presentación
  // -----------------------------------------------------------------

  static String textoEstado(String? status) {
    switch (status) {
      case 'FINISHED':
        return 'Finalizado';
      case 'RELEASING':
        return 'En emisión';
      case 'NOT_YET_RELEASED':
        return 'Próximamente';
      case 'CANCELLED':
        return 'Cancelado';
      case 'HIATUS':
        return 'En pausa';
      default:
        return 'Desconocido';
    }
  }

  static String limpiarDescripcion(String? raw) {
    if (raw == null || raw.trim().isEmpty) {
      return 'Sin sinopsis disponible.';
    }
    var texto = raw.replaceAll(
      RegExp(r'<br\s*/?>', caseSensitive: false),
      '\n',
    );
    texto = texto.replaceAll(RegExp(r'<[^>]*>'), '');
    texto = texto
        .replaceAll('&amp;', '&')
        .replaceAll('&lt;', '<')
        .replaceAll('&gt;', '>')
        .replaceAll('&quot;', '"')
        .replaceAll('&#39;', "'")
        .replaceAll('&nbsp;', ' ');
    texto = texto.replaceAll(RegExp(r'\n\s*\n+'), '\n\n').trim();
    if (texto.isEmpty) return 'Sin sinopsis disponible.';
    return texto;
  }

  // -----------------------------------------------------------------
  // UI
  // -----------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    final anime = _anime;
    return Scaffold(
      appBar: AppBar(
        title: Text(anime?.tituloDisplay ?? 'Detalle'),
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_cargandoDetalle) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_errorDetalle != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.cloud_off_outlined, size: 48),
              const SizedBox(height: 12),
              Text(_errorDetalle!, textAlign: TextAlign.center),
              const SizedBox(height: 12),
              FilledButton.icon(
                onPressed: _cargarDetalle,
                icon: const Icon(Icons.refresh),
                label: const Text('Reintentar'),
              ),
            ],
          ),
        ),
      );
    }
    final anime = _anime;
    if (anime == null) {
      return const Center(child: Text('No se pudo cargar el anime.'));
    }

    // Total conocido o inferido (en emisión: nextAiring - 1, como
    // mínimo lo ya visto). 0 = sin episodios confirmados todavía.
    final actual = _entrada?.episodioActual ?? 0;
    final visibles = anime.episodiosVisibles(actual);
    final totalConocido = anime.episodios != null && anime.episodios! > 0;
    return CustomScrollView(
      slivers: [
        SliverToBoxAdapter(child: _buildHeader(anime)),
        SliverToBoxAdapter(child: _buildAcciones(anime)),
        SliverToBoxAdapter(child: _buildTituloEpisodios(anime)),
        if (visibles <= 0)
          const SliverToBoxAdapter(
            child: Padding(
              padding: EdgeInsets.fromLTRB(16, 0, 16, 24),
              child: Text(
                'En emisión, todavía no hay episodios confirmados.',
              ),
            ),
          )
        else ...[
          if (!totalConocido)
            const SliverToBoxAdapter(
              child: Padding(
                padding: EdgeInsets.fromLTRB(16, 0, 16, 4),
                child: Text(
                  'En emisión: se listan los episodios ya emitidos.',
                ),
              ),
            ),
          SliverList.builder(
            itemCount: visibles,
            itemBuilder: (context, i) => _buildFilaEpisodio(i + 1),
          ),
        ],
      ],
    );
  }

  Widget _buildHeader(Anime anime) {
    final scheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AnimeCoverImage(
            url: anime.coverImageUrl,
            width: 140,
            height: 200,
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  anime.tituloDisplay,
                  style: textTheme.headlineSmall,
                ),
                if (anime.generos.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 6,
                    runSpacing: 6,
                    children: anime.generos
                        .map((g) => Chip(
                              label: Text(g),
                              visualDensity: VisualDensity.compact,
                              padding: EdgeInsets.zero,
                            ))
                        .toList(),
                  ),
                ],
                const SizedBox(height: 8),
                Text(
                  limpiarDescripcion(anime.descripcion),
                  style: textTheme.bodyMedium,
                ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 16,
                  runSpacing: 8,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(
                          Icons.star,
                          size: 16,
                          color: Colors.amber,
                        ),
                        const SizedBox(width: 4),
                        Text(
                          anime.averageScore != null
                              ? '${anime.averageScore}'
                              : '—',
                          style: textTheme.bodyMedium,
                        ),
                      ],
                    ),
                    Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          Icons.tv_outlined,
                          size: 16,
                          color: scheme.onSurfaceVariant,
                        ),
                        const SizedBox(width: 4),
                        Text(
                          anime.episodios != null
                              ? '${anime.episodios} eps'
                              : 'En emisión',
                          style: textTheme.bodyMedium,
                        ),
                      ],
                    ),
                    Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          Icons.info_outline,
                          size: 16,
                          color: scheme.onSurfaceVariant,
                        ),
                        const SizedBox(width: 4),
                        Text(
                          textoEstado(anime.status),
                          style: textTheme.bodyMedium,
                        ),
                      ],
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAcciones(Anime anime) {
    final enBiblioteca = _entrada != null;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
      child: Row(
        children: [
          Expanded(
            child: _cargandoBiblioteca
                ? const FilledButton(
                    onPressed: null,
                    child: Text('Cargando…'),
                  )
                : enBiblioteca
                    ? OutlinedButton.icon(
                        onPressed:
                            _guardando ? null : _abrirModalBiblioteca,
                        icon: const Icon(Icons.check),
                        label: const Text('En mi biblioteca'),
                      )
                    : FilledButton.icon(
                        onPressed:
                            _guardando ? null : _abrirModalBiblioteca,
                        icon: const Icon(Icons.add),
                        label: const Text('Agregar a mi biblioteca'),
                      ),
          ),
          const SizedBox(width: 12),
          IconButton(
            tooltip: _esFavorito
                ? 'Quitar de favoritos'
                : 'Marcar como favorito',
            isSelected: _esFavorito,
            selectedIcon: const Icon(Icons.favorite, color: Colors.red),
            icon: const Icon(Icons.favorite_outline),
            onPressed: () => setState(
              () => _esFavorito = !_esFavorito,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTituloEpisodios(Anime anime) {
    final actual = _entrada?.episodioActual ?? 0;
    final total = anime.episodios;
    final String? subtitulo;
    if (total != null && total > 0) {
      subtitulo = '$actual/$total vistos';
    } else {
      final visibles = anime.episodiosVisibles(actual);
      subtitulo = visibles > 0 ? '$actual/$visibles vistos' : null;
    }
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Text(
            'Episodios',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          if (subtitulo != null) ...[
            const SizedBox(width: 8),
            Text(
              subtitulo,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildFilaEpisodio(int numero) {
    final scheme = Theme.of(context).colorScheme;
    final actual = _entrada?.episodioActual ?? 0;
    final visto = numero <= actual;
    final esProximo = numero == actual + 1;

    final Widget iconoEstado;
    if (visto) {
      iconoEstado = const Icon(Icons.check_circle, color: Colors.green);
    } else if (esProximo) {
      iconoEstado = Icon(Icons.play_circle_fill, color: scheme.primary);
    } else {
      iconoEstado =
          Icon(Icons.circle_outlined, color: scheme.onSurfaceVariant);
    }

    return ListTile(
      key: ValueKey('episodio-$numero'),
      tileColor: esProximo
          ? scheme.primaryContainer.withValues(alpha: 0.35)
          : null,
      contentPadding:
          const EdgeInsets.symmetric(horizontal: 16, vertical: 2),
      leading: iconoEstado,
      title: Text('Episodio $numero'),
      subtitle: visto
          ? const Text('Visto')
          : esProximo
              ? Text(
                  'Próximo a ver',
                  style: TextStyle(color: scheme.primary),
                )
              : null,
      trailing: IconButton(
        tooltip: 'Ver episodio',
        icon: const Icon(Icons.play_arrow),
        onPressed: () => _abrirReproductor(numero),
      ),
    );
  }
}

import 'package:flutter/material.dart';

import '../data/biblioteca_repository.dart';
import '../models/entrada_biblioteca.dart';
import '../services/anilist_service.dart';
import '../widgets/anime_image.dart';
import 'detalle_anime_screen.dart';

/// Pantalla "Mi biblioteca": lista lo guardado en SQLite.
///
/// Lee con [BibliotecaRepository.obtenerTodas] y muestra una fila por
/// anime con portada, título y progreso. El tap abre el detalle (que
/// trae el [Anime] completo por red) y al volver se recarga la lista,
/// por si se quitó el anime o cambió el progreso.
class BibliotecaScreen extends StatefulWidget {
  final BibliotecaRepository? repository;

  /// Servicio para el detalle que se abre desde cada fila.
  /// Inyectable en tests (por defecto el detalle crea el propio).
  final AnilistService? service;

  const BibliotecaScreen({super.key, this.repository, this.service});

  @override
  State<BibliotecaScreen> createState() => BibliotecaScreenState();
}

class BibliotecaScreenState extends State<BibliotecaScreen> {
  late final BibliotecaRepository _repository;
  late Future<List<EntradaBiblioteca>> _futuro;

  /// Filtro activo. `null` significa "Todos" (default al entrar).
  EstadoBiblioteca? _filtroActivo;

  /// Conteos por estado para los chips. Se calculan en memoria sobre
  /// `obtenerTodas()` (una sola consulta) para no disparar una query
  /// por chip. La lista visible sí usa `obtenerPorEstado` cuando hay
  /// filtro (requisito del módulo).
  Map<EstadoBiblioteca, int> _conteos = {
    for (final estado in EstadoBiblioteca.values) estado: 0,
  };
  int _total = 0;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? BibliotecaRepository();
    _futuro = _cargar();
    // _cargar() actualiza _conteos/_total al completarse, pero la barra
    // de filtros vive fuera del FutureBuilder: este then la refresca.
    _futuro.then(
      (_) {
        if (mounted) setState(() {});
      },
      onError: (error, stack) {
        if (mounted) setState(() {});
      },
    );
  }

  /// Relee la base y refresca la UI. Lo llama el [AppShell] cada vez
  /// que se selecciona esta sección, el pull-to-refresh, el botón de
  /// reintentar, esta misma pantalla al volver del detalle y el cambio
  /// de filtro. Respeta [_filtroActivo]: no lo resetea a "Todos".
  Future<void> recargar() async {
    final futuro = _cargar();
    // Bloque (no `=>`): la asignación devuelve el Future y setState
    // exige un callback síncrono que devuelva void.
    setState(() {
      _futuro = futuro;
    });
    try {
      await futuro;
    } finally {
      // Refresca la barra de filtros (conteos) que está fuera del
      // FutureBuilder. El `finally` cubre también el caso de error.
      if (mounted) setState(() {});
    }
  }

  Future<List<EntradaBiblioteca>> _cargar() async {
    try {
      // Una sola lectura total para los contadores de los chips.
      final todas = await _repository.obtenerTodas();
      final conteos = {
        for (final estado in EstadoBiblioteca.values) estado: 0,
      };
      for (final entrada in todas) {
        conteos[entrada.estado] = (conteos[entrada.estado] ?? 0) + 1;
      }
      _conteos = conteos;
      _total = todas.length;
      if (_filtroActivo == null) {
        debugPrint(
          '[Biblioteca] obtenerTodas() → ${todas.length} entradas: '
          '${todas.map((e) => e.animeId).toList()}',
        );
        return todas;
      }
      final filtradas =
          await _repository.obtenerPorEstado(_filtroActivo!);
      debugPrint(
        '[Biblioteca] obtenerPorEstado(${_filtroActivo!.name}) → '
        '${filtradas.length} entradas: '
        '${filtradas.map((e) => e.animeId).toList()}',
      );
      return filtradas;
    } catch (e) {
      debugPrint('[Biblioteca] carga FALLÓ (filtro=${_filtroActivo?.name ?? 'todos'}): $e');
      rethrow;
    }
  }

  Future<void> _alSeleccionarFiltro(EstadoBiblioteca? filtro) async {
    if (_filtroActivo == filtro) return;
    _filtroActivo = filtro;
    // recargar() hace los setState necesarios (lista + conteos).
    await recargar();
  }

  Future<void> _abrirDetalle(int animeId) async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => DetalleAnimeScreen(
          animeId: animeId,
          service: widget.service,
        ),
      ),
    );
    if (!mounted) return;
    // Al volver (p. ej. se quitó de la biblioteca o avanzó episodios)
    // la lista puede haber cambiado: releer.
    await recargar();
  }

  static String _textoEstado(EstadoBiblioteca estado) {
    switch (estado) {
      case EstadoBiblioteca.viendo:
        return 'Viendo';
      case EstadoBiblioteca.completado:
        return 'Completado';
      case EstadoBiblioteca.pendiente:
        return 'Pendiente';
      case EstadoBiblioteca.abandonado:
        return 'Abandonado';
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _buildBarraFiltros(),
            Expanded(
              child: FutureBuilder<List<EntradaBiblioteca>>(
                future: _futuro,
                builder: (context, snapshot) {
                  if (snapshot.connectionState ==
                      ConnectionState.waiting) {
                    return const Center(
                        child: CircularProgressIndicator());
                  }
                  if (snapshot.hasError) {
                    return Center(
                      child: Padding(
                        padding: const EdgeInsets.all(24),
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Icon(Icons.cloud_off_outlined, size: 48),
                            const SizedBox(height: 12),
                            Text(
                              'No se pudo leer tu biblioteca: ${snapshot.error}',
                              textAlign: TextAlign.center,
                            ),
                            const SizedBox(height: 12),
                            FilledButton.icon(
                              onPressed: recargar,
                              icon: const Icon(Icons.refresh),
                              label: const Text('Reintentar'),
                            ),
                          ],
                        ),
                      ),
                    );
                  }
                  final entradas = snapshot.data ?? const [];
                  if (entradas.isEmpty) {
                    return RefreshIndicator(
                      onRefresh: recargar,
                      child: ListView(
                        padding: const EdgeInsets.only(top: 24),
                        children: [
                          const Icon(
                            Icons.video_library_outlined,
                            size: 64,
                          ),
                          const SizedBox(height: 16),
                          Center(
                            child: Text(
                              _mensajeVacio(),
                              style: const TextStyle(fontSize: 18),
                            ),
                          ),
                          const SizedBox(height: 8),
                          const Center(
                            child: Text(
                              'Agregá animes desde su pantalla de detalle.',
                            ),
                          ),
                        ],
                      ),
                    );
                  }
                  return RefreshIndicator(
                    onRefresh: recargar,
                    child: ListView(
                      padding: const EdgeInsets.only(top: 8, bottom: 24),
                      children: [
                        Padding(
                          padding:
                              const EdgeInsets.fromLTRB(16, 8, 16, 8),
                          child: Text(
                            'Mi biblioteca (${entradas.length})',
                            style:
                                Theme.of(context).textTheme.titleLarge,
                          ),
                        ),
                        ...entradas.map(_buildFila),
                      ],
                    ),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// Fila horizontal de filtros con contadores. "Todos" equivale a
  /// [_filtroActivo] == null y es el default al entrar.
  Widget _buildBarraFiltros() {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
      child: Row(
        children: [
          ChoiceChip(
            label: Text('Todos ($_total)'),
            selected: _filtroActivo == null,
            onSelected: (seleccionado) {
              if (seleccionado) _alSeleccionarFiltro(null);
            },
          ),
          for (final estado in EstadoBiblioteca.values) ...[
            const SizedBox(width: 8),
            ChoiceChip(
              label: Text(
                '${_textoEstado(estado)} (${_conteos[estado] ?? 0})',
              ),
              selected: _filtroActivo == estado,
              onSelected: (seleccionado) {
                if (seleccionado) _alSeleccionarFiltro(estado);
              },
            ),
          ],
        ],
      ),
    );
  }

  /// Mensaje de vacío: genérico en "Todos", específico por filtro si
  /// hay uno activo (p. ej. "No tenés animes en Pendiente todavía").
  String _mensajeVacio() {
    final filtro = _filtroActivo;
    if (filtro == null) return 'Tu biblioteca está vacía';
    return 'No tenés animes en ${_textoEstado(filtro)} todavía';
  }

  Widget _buildFila(EntradaBiblioteca entrada) {
    final progreso = entrada.episodiosTotales != null
        ? '${entrada.episodioActual}/${entrada.episodiosTotales} eps'
        : '${entrada.episodioActual} vistos';
    return ListTile(
      contentPadding:
          const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      leading: AnimeCoverImage(
        url: entrada.imagenPortada,
        width: 48,
        height: 64,
      ),
      title: Text(
        entrada.tituloAnime,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
      ),
      subtitle: Text(
        '$progreso  ·  ${_textoEstado(entrada.estado)}',
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
      ),
      trailing: const Icon(Icons.chevron_right),
      onTap: () => _abrirDetalle(entrada.animeId),
    );
  }
}

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

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? BibliotecaRepository();
    _futuro = _cargar();
  }

  /// Relee la base y refresca la UI. Lo llama el [AppShell] cada vez
  /// que se selecciona esta sección, el pull-to-refresh, el botón de
  /// reintentar y esta misma pantalla al volver del detalle.
  Future<void> recargar() async {
    final futuro = _cargar();
    // Bloque (no `=>`): la asignación devuelve el Future y setState
    // exige un callback síncrono que devuelva void.
    setState(() {
      _futuro = futuro;
    });
    await futuro;
  }

  Future<List<EntradaBiblioteca>> _cargar() async {
    try {
      final entradas = await _repository.obtenerTodas();
      debugPrint(
        '[Biblioteca] obtenerTodas() → ${entradas.length} entradas: '
        '${entradas.map((e) => e.animeId).toList()}',
      );
      return entradas;
    } catch (e) {
      debugPrint('[Biblioteca] obtenerTodas() FALLÓ: $e');
      rethrow;
    }
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
        child: FutureBuilder<List<EntradaBiblioteca>>(
          future: _futuro,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
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
                  children: const [
                    Icon(
                      Icons.video_library_outlined,
                      size: 64,
                    ),
                    SizedBox(height: 16),
                    Center(
                      child: Text(
                        'Tu biblioteca está vacía',
                        style: TextStyle(fontSize: 18),
                      ),
                    ),
                    SizedBox(height: 8),
                    Center(
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
                    padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
                    child: Text(
                      'Mi biblioteca (${entradas.length})',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                  ),
                  ...entradas.map(_buildFila),
                ],
              ),
            );
          },
        ),
      ),
    );
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

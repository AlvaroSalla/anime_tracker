import 'dart:async';

import 'package:flutter/material.dart';

import '../models/anime.dart';
import '../services/anilist_service.dart';
import '../widgets/anime_card.dart';
import '../widgets/anime_list_tile.dart';
import 'detalle_anime_screen.dart';

/// Pantalla de inicio: búsqueda + "Recomendado para vos" (carrusel)
/// + "Más vistos según AniList" (lista vertical).
///
/// El servicio se inyecta para poder usar un fake en tests. El dueño
/// del servicio es quien la construye (el `AppShell`); esta pantalla
/// nunca lo cierra.
class InicioScreen extends StatefulWidget {
  final AnilistService service;

  const InicioScreen({super.key, required this.service});

  @override
  State<InicioScreen> createState() => _InicioScreenState();
}

class _InicioScreenState extends State<InicioScreen> {
  // ---- Estado del trending ----
  bool _cargando = true;
  String? _error;
  List<Anime> _trending = [];

  // ---- Estado de la búsqueda ----
  final _searchController = TextEditingController();
  Timer? _debounce;
  int _searchToken = 0;
  bool _buscando = false;
  String? _searchError;
  List<Anime> _resultados = [];

  bool get _busquedaActiva => _searchController.text.trim().isNotEmpty;

  @override
  void initState() {
    super.initState();
    _cargarTrending();
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _cargarTrending() async {
    setState(() {
      _cargando = true;
      _error = null;
    });
    try {
      final datos = await widget.service.obtenerTrending();
      if (!mounted) return;
      setState(() {
        _trending = datos;
        _cargando = false;
      });
    } on AnilistException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _cargando = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = 'Error inesperado: $e';
        _cargando = false;
      });
    }
  }

  void _onSearchChanged(String texto) {
    _debounce?.cancel();
    // Al vaciar el campo se limpia el panel e invalidan búsquedas en vuelo.
    if (texto.trim().isEmpty) {
      _searchToken++;
      setState(() {
        _buscando = false;
        _searchError = null;
        _resultados = [];
      });
      return;
    }
    // Muestra el spinner enseguida; el debounce evita pegar a la API
    // en cada tecla.
    setState(() {
      _buscando = true;
      _searchError = null;
    });
    _debounce = Timer(const Duration(milliseconds: 500), () {
      _ejecutarBusqueda(texto.trim());
    });
  }

  Future<void> _ejecutarBusqueda(String query) async {
    final token = ++_searchToken;
    setState(() {
      _buscando = true;
      _searchError = null;
    });
    try {
      final datos = await widget.service.buscarAnime(query);
      if (!mounted || token != _searchToken) return;
      setState(() {
        _resultados = datos;
        _buscando = false;
      });
    } on AnilistException catch (e) {
      if (!mounted || token != _searchToken) return;
      setState(() {
        _searchError = e.message;
        _buscando = false;
      });
    } catch (e) {
      if (!mounted || token != _searchToken) return;
      setState(() {
        _searchError = 'Error inesperado: $e';
        _buscando = false;
      });
    }
  }

  void _limpiarBusqueda() {
    _debounce?.cancel();
    _searchToken++; // invalida búsquedas en vuelo
    _searchController.clear();
    setState(() {
      _buscando = false;
      _searchError = null;
      _resultados = [];
    });
  }

  /// Abre el detalle del [anime]. Se pasa el objeto completo para no
  /// esperar otra petición. Al volver no se refresca nada: el refresh
  /// de biblioteca se resuelve en su propio módulo.
  void _abrirDetalle(Anime anime) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => DetalleAnimeScreen(
          animeId: anime.id,
          animeInicial: anime,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Stack(
          children: [
            // Contenido principal (con espacio arriba para el buscador).
            _buildContenido(),
            // Buscador fijo arriba + panel de resultados superpuesto.
            Positioned(
              top: 0,
              left: 0,
              right: 0,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  _buildBuscador(),
                  if (_busquedaActiva) _buildPanelResultados(),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildBuscador() {
    return Container(
      color: Theme.of(context).scaffoldBackgroundColor,
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
      child: TextField(
        controller: _searchController,
        onChanged: _onSearchChanged,
        textInputAction: TextInputAction.search,
        onSubmitted: (texto) {
          _debounce?.cancel();
          if (texto.trim().isNotEmpty) _ejecutarBusqueda(texto.trim());
        },
        decoration: InputDecoration(
          hintText: 'Buscar anime…',
          prefixIcon: const Icon(Icons.search),
          suffixIcon: _busquedaActiva
              ? IconButton(
                  tooltip: 'Limpiar',
                  icon: const Icon(Icons.clear),
                  onPressed: _limpiarBusqueda,
                )
              : null,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          filled: true,
        ),
      ),
    );
  }

  Widget _buildPanelResultados() {
    return Container(
      constraints: const BoxConstraints(maxHeight: 320),
      margin: const EdgeInsets.symmetric(horizontal: 16),
      child: Material(
        elevation: 4,
        borderRadius: BorderRadius.circular(12),
        child: _buildContenidoPanel(),
      ),
    );
  }

  Widget _buildContenidoPanel() {
    if (_buscando) {
      return const Padding(
        padding: EdgeInsets.all(24),
        child: Center(child: CircularProgressIndicator()),
      );
    }
    if (_searchError != null) {
      return Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Expanded(child: Text(_searchError!)),
            TextButton(
              onPressed: () => _ejecutarBusqueda(
                _searchController.text.trim(),
              ),
              child: const Text('Reintentar'),
            ),
          ],
        ),
      );
    }
    if (_resultados.isEmpty) {
      return const Padding(
        padding: EdgeInsets.all(24),
        child: Center(child: Text('Sin resultados')),
      );
    }
    return ListView.separated(
      shrinkWrap: true,
      padding: const EdgeInsets.symmetric(vertical: 8),
      itemCount: _resultados.length,
      separatorBuilder: (_, _) => const Divider(height: 1, indent: 72),
      itemBuilder: (context, i) => AnimeListTile(
        anime: _resultados[i],
        onTap: () => _abrirDetalle(_resultados[i]),
      ),
    );
  }

  Widget _buildContenido() {
    if (_cargando) {
      return const Padding(
        // Deja lugar al buscador fijo.
        padding: EdgeInsets.only(top: 76),
        child: Center(child: CircularProgressIndicator()),
      );
    }
    if (_error != null) {
      return Padding(
        padding: const EdgeInsets.only(top: 76, left: 24, right: 24),
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.cloud_off_outlined, size: 48),
              const SizedBox(height: 12),
              Text(
                _error!,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 12),
              FilledButton.icon(
                onPressed: _cargarTrending,
                icon: const Icon(Icons.refresh),
                label: const Text('Reintentar'),
              ),
            ],
          ),
        ),
      );
    }
    return ListView(
      // Espacio para el buscador fijo + aire.
      padding: const EdgeInsets.only(top: 84, bottom: 24),
      children: [
        _buildTituloSeccion('Recomendado para vos'),
        SizedBox(
          height: 250,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 12),
            itemCount: _trending.length,
            separatorBuilder: (_, _) => const SizedBox(width: 4),
            itemBuilder: (context, i) => AnimeCard(
              anime: _trending[i],
              onTap: () => _abrirDetalle(_trending[i]),
            ),
          ),
        ),
        const SizedBox(height: 16),
        _buildTituloSeccion('Más vistos según AniList'),
        ..._trending.map(
          (anime) => AnimeListTile(
            anime: anime,
            onTap: () => _abrirDetalle(anime),
          ),
        ),
      ],
    );
  }

  Widget _buildTituloSeccion(String texto) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
      child: Text(
        texto,
        style: Theme.of(context).textTheme.titleLarge,
      ),
    );
  }
}

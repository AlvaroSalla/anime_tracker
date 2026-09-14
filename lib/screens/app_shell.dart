import 'package:flutter/material.dart';

import '../services/anilist_service.dart';
import 'inicio_screen.dart';

/// Estructura general de la app: [NavigationRail] fijo a la izquierda
/// + contenido con [IndexedStack] (mantiene el estado de cada sección
/// al cambiar, sin recrear los widgets).
class AppShell extends StatefulWidget {
  /// Servicio compartido con las pantallas. Si no se pasa, el shell
  /// crea uno propio (y lo cierra al destruirse). Inyectable en tests.
  final AnilistService? service;

  const AppShell({super.key, this.service});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  late final AnilistService _service;
  late final bool _poseeServicio;
  late final List<Widget> _secciones;

  int _seccion = 0;

  /// Último destino del rail (0-4). Se guarda aparte porque
  /// Configuración (5) vive en el trailing y el rail siempre necesita
  /// un selectedIndex válido.
  int _indiceRail = 0;

  @override
  void initState() {
    super.initState();
    _poseeServicio = widget.service == null;
    _service = widget.service ?? AnilistService();
    // Se crean una sola vez: el IndexedStack las mantiene vivas y
    // conserva su estado (scroll, texto buscado, datos cargados).
    // Índices 0-4 = destinos del rail, 5 = Configuración (trailing).
    _secciones = [
      InicioScreen(service: _service),
      const SeccionPlaceholder(
        titulo: 'Mi biblioteca',
        icono: Icons.video_library_outlined,
      ),
      const SeccionPlaceholder(
        titulo: 'Viendo',
        icono: Icons.play_circle_outline,
      ),
      const SeccionPlaceholder(
        titulo: 'Favoritos',
        icono: Icons.favorite_outline,
      ),
      const SeccionPlaceholder(
        titulo: 'Historial',
        icono: Icons.history,
      ),
      const SeccionPlaceholder(
        titulo: 'Configuración',
        icono: Icons.settings_outlined,
      ),
    ];
  }

  @override
  void dispose() {
    if (_poseeServicio) _service.dispose();
    super.dispose();
  }

  static const _destinos = [
    NavigationRailDestination(
      icon: Icon(Icons.home_outlined),
      selectedIcon: Icon(Icons.home),
      label: Text('Inicio'),
    ),
    NavigationRailDestination(
      icon: Icon(Icons.video_library_outlined),
      selectedIcon: Icon(Icons.video_library),
      label: Text('Mi biblioteca'),
    ),
    NavigationRailDestination(
      icon: Icon(Icons.play_circle_outline),
      selectedIcon: Icon(Icons.play_circle),
      label: Text('Viendo'),
    ),
    NavigationRailDestination(
      icon: Icon(Icons.favorite_outline),
      selectedIcon: Icon(Icons.favorite),
      label: Text('Favoritos'),
    ),
    NavigationRailDestination(
      icon: Icon(Icons.history_outlined),
      selectedIcon: Icon(Icons.history),
      label: Text('Historial'),
    ),
  ];

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        // En desktop (ventana ancha) el rail va siempre expandido.
        final expandido = constraints.maxWidth >= 900;
        final scheme = Theme.of(context).colorScheme;
        // Configuración va separada abajo (patrón estándar): el Divider
        // hace de separador visual y el trailing queda fijado al pie.
        final configuracionSeleccionada = _seccion == 5;
        final colorConfig = configuracionSeleccionada
            ? scheme.primary
            : scheme.onSurfaceVariant;
        return Scaffold(
          body: Row(
            children: [
              NavigationRail(
                extended: expandido,
                minExtendedWidth: 210,
                selectedIndex: _indiceRail,
                onDestinationSelected: (indice) => setState(() {
                  _seccion = indice;
                  _indiceRail = indice;
                }),
                labelType: expandido
                    ? NavigationRailLabelType.none
                    : NavigationRailLabelType.all,
                leading: expandido
                    ? const Padding(
                        padding: EdgeInsets.fromLTRB(16, 16, 16, 8),
                        child: Text(
                          'Anime Tracker',
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      )
                    : const SizedBox(height: 16),
                trailing: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const SizedBox(
                      width: 48,
                      child: Divider(),
                    ),
                    InkWell(
                      borderRadius: BorderRadius.circular(16),
                      onTap: () => setState(() => _seccion = 5),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 16,
                          vertical: 12,
                        ),
                        child: expandido
                            ? Row(
                                children: [
                                  Icon(
                                    configuracionSeleccionada
                                        ? Icons.settings
                                        : Icons.settings_outlined,
                                    color: colorConfig,
                                  ),
                                  const SizedBox(width: 12),
                                  Text(
                                    'Configuración',
                                    style: TextStyle(color: colorConfig),
                                  ),
                                ],
                              )
                            : Column(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Icon(
                                    configuracionSeleccionada
                                        ? Icons.settings
                                        : Icons.settings_outlined,
                                    color: colorConfig,
                                  ),
                                  Text(
                                    'Configuración',
                                    style: TextStyle(
                                      fontSize: 12,
                                      color: colorConfig,
                                    ),
                                  ),
                                ],
                              ),
                      ),
                    ),
                    const SizedBox(height: 12),
                  ],
                ),
                destinations: _destinos,
              ),
              const VerticalDivider(width: 1),
              Expanded(
                child: IndexedStack(
                  index: _seccion,
                  children: _secciones,
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

/// Placeholder temporal para las secciones aún no implementadas.
class SeccionPlaceholder extends StatelessWidget {
  final String titulo;
  final IconData icono;

  const SeccionPlaceholder({
    super.key,
    required this.titulo,
    required this.icono,
  });

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icono, size: 64, color: textTheme.bodySmall?.color),
          const SizedBox(height: 16),
          Text(titulo, style: textTheme.headlineSmall),
          const SizedBox(height: 8),
          const Text('Próximamente'),
        ],
      ),
    );
  }
}

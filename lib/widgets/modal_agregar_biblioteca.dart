import 'package:flutter/material.dart';

import '../models/anime.dart';
import '../models/entrada_biblioteca.dart';

/// Resultado del modal de biblioteca.
sealed class ResultadoModalBiblioteca {
  const ResultadoModalBiblioteca();
}

/// El usuario confirmó: guardar esta entrada (agregar o actualizar,
/// lo decide quien abrió el modal según si ya existía).
class GuardarBiblioteca extends ResultadoModalBiblioteca {
  final EntradaBiblioteca entrada;

  const GuardarBiblioteca(this.entrada);
}

/// El usuario pidió quitar el anime de la biblioteca (ya confirmado
/// dentro del modal). Solo posible en modo edición.
class QuitarBiblioteca extends ResultadoModalBiblioteca {
  const QuitarBiblioteca();
}

/// Abre el modal de agregar/editar en biblioteca.
///
/// En desktop se usa [showDialog] (más nativo que el bottom sheet).
/// Devuelve [GuardarBiblioteca] al confirmar, [QuitarBiblioteca] si se
/// quitó (solo edición) o `null` si se canceló.
Future<ResultadoModalBiblioteca?> mostrarModalAgregarBiblioteca({
  required BuildContext context,
  required Anime anime,
  EntradaBiblioteca? entradaExistente,
}) {
  return showDialog<ResultadoModalBiblioteca>(
    context: context,
    builder: (dialogContext) => Dialog(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 480),
        child: ModalAgregarBiblioteca(
          anime: anime,
          entradaExistente: entradaExistente,
          onGuardar: (entrada) => Navigator.of(dialogContext).pop(
            GuardarBiblioteca(entrada),
          ),
          onCancelar: () => Navigator.of(dialogContext).pop(),
          onQuitar: entradaExistente == null
              ? null
              : () async {
                  final confirmar = await showDialog<bool>(
                    context: dialogContext,
                    builder: (context) => AlertDialog(
                      title: const Text('Quitar de la biblioteca'),
                      content: Text(
                        '¿Querés sacar "${entradaExistente.tituloAnime}" '
                        'de tu biblioteca?',
                      ),
                      actions: [
                        TextButton(
                          onPressed: () =>
                              Navigator.of(context).pop(false),
                          child: const Text('Cancelar'),
                        ),
                        FilledButton(
                          onPressed: () =>
                              Navigator.of(context).pop(true),
                          child: const Text('Quitar'),
                        ),
                      ],
                    ),
                  );
                  if (confirmar == true && dialogContext.mounted) {
                    Navigator.of(dialogContext).pop(
                      const QuitarBiblioteca(),
                    );
                  }
                },
        ),
      ),
    ),
  );
}

/// Formulario de agregar/editar en biblioteca.
///
/// - Estado requerido ([SegmentedButton] con las 4 opciones).
/// - Episodio numérico solo para Viendo/Abandonado, validado contra el
///   total conocido. Completado autocompleta con el total (deshabilitado
///   si el total es `null` por estar en emisión). Pendiente fija 0.
/// - Calificación opcional de 1 a 10 (se puede saltear/quitar).
/// - En modo edición se pre-cargan los valores actuales (conservando
///   [EntradaBiblioteca.fechaAgregado]) y se ofrece quitar.
class ModalAgregarBiblioteca extends StatefulWidget {
  final Anime anime;
  final EntradaBiblioteca? entradaExistente;
  final ValueChanged<EntradaBiblioteca> onGuardar;
  final VoidCallback onCancelar;

  /// Si es `null` se oculta el botón de quitar (modo agregar).
  final VoidCallback? onQuitar;

  const ModalAgregarBiblioteca({
    super.key,
    required this.anime,
    this.entradaExistente,
    required this.onGuardar,
    required this.onCancelar,
    this.onQuitar,
  });

  @override
  State<ModalAgregarBiblioteca> createState() =>
      _ModalAgregarBibliotecaState();
}

class _ModalAgregarBibliotecaState extends State<ModalAgregarBiblioteca> {
  EstadoBiblioteca? _estado;
  late final TextEditingController _episodioController;
  int? _calificacion;

  @override
  void initState() {
    super.initState();
    final existente = widget.entradaExistente;
    _estado = existente?.estado;
    // En edición se pre-carga; al agregar arranca vacío para forzar
    // una elección consciente del episodio.
    _episodioController = TextEditingController(
      text: existente == null ? '' : '${existente.episodioActual}',
    );
    _calificacion = existente?.calificacionPersonal;
  }

  @override
  void dispose() {
    _episodioController.dispose();
    super.dispose();
  }

  /// Total conocido de episodios (`null` = en emisión, desconocido).
  int? get _total {
    final total = widget.anime.episodios;
    return total != null && total > 0 ? total : null;
  }

  bool get _esEdicion => widget.entradaExistente != null;

  bool get _pideEpisodio =>
      _estado == EstadoBiblioteca.viendo ||
      _estado == EstadoBiblioteca.abandonado;

  /// Error inline del campo de episodio, o `null` si es válido.
  /// Solo aplica cuando el campo está visible.
  String? get _errorEpisodio {
    if (!_pideEpisodio) return null;
    final texto = _episodioController.text.trim();
    final numero = int.tryParse(texto);
    if (numero == null) return 'Ingresá un número de episodio válido.';
    if (numero < 0) return 'El episodio no puede ser negativo.';
    final total = _total;
    if (total != null && numero > total) {
      return 'No puede ser mayor al total ($total).';
    }
    return null;
  }

  bool get _puedeGuardar => _estado != null && _errorEpisodio == null;

  EntradaBiblioteca _construirEntrada() {
    final total = _total;
    final episodio = switch (_estado!) {
      // Completado solo se puede elegir con total conocido.
      EstadoBiblioteca.completado => total ?? 0,
      EstadoBiblioteca.pendiente => 0,
      EstadoBiblioteca.viendo || EstadoBiblioteca.abandonado =>
        int.tryParse(_episodioController.text.trim()) ?? 0,
    };
    return EntradaBiblioteca(
      animeId: widget.anime.id,
      tituloAnime: widget.anime.tituloDisplay,
      imagenPortada: widget.anime.coverImageUrl,
      estado: _estado!,
      episodioActual: episodio,
      episodiosTotales: total,
      // En edición se conserva la fecha original de alta.
      fechaAgregado: widget.entradaExistente?.fechaAgregado,
      calificacionPersonal: _calificacion,
    );
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
    final textTheme = Theme.of(context).textTheme;
    final total = _total;
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            _esEdicion
                ? 'Editar en mi biblioteca'
                : 'Agregar a mi biblioteca',
            style: textTheme.titleLarge,
          ),
          const SizedBox(height: 4),
          Text(
            total != null
                ? '${widget.anime.tituloDisplay} · $total episodios'
                : '${widget.anime.tituloDisplay} · En emisión',
            style: textTheme.bodyMedium,
          ),
          const SizedBox(height: 16),
          Text('Estado', style: textTheme.titleSmall),
          const SizedBox(height: 8),
          SegmentedButton<EstadoBiblioteca>(
            showSelectedIcon: false,
            style: const ButtonStyle(
              visualDensity: VisualDensity.compact,
            ),
            // Al agregar arranca sin selección (Guardar exige elegir):
            // hay que permitir el conjunto vacío explícitamente.
            emptySelectionAllowed: true,
            segments: EstadoBiblioteca.values
                .map(
                  (estado) => ButtonSegment(
                    value: estado,
                    label: Text(_textoEstado(estado)),
                    // Sin total conocido no se puede completar.
                    enabled: estado != EstadoBiblioteca.completado ||
                        total != null,
                  ),
                )
                .toList(),
            selected: _estado == null ? const {} : {_estado!},
            onSelectionChanged: (seleccion) => setState(() {
              _estado = seleccion.single;
            }),
          ),
          if (total == null) ...[
            const SizedBox(height: 8),
            Text(
              'Completado no disponible: total desconocido (en emisión).',
              style: textTheme.bodySmall,
            ),
          ],
          if (_pideEpisodio) ...[
            const SizedBox(height: 16),
            Text('Episodio actual', style: textTheme.titleSmall),
            const SizedBox(height: 8),
            TextField(
              controller: _episodioController,
              keyboardType: TextInputType.number,
              decoration: InputDecoration(
                hintText: total != null ? '0 – $total' : '0 o más',
                border: const OutlineInputBorder(),
                errorText: _errorEpisodio,
              ),
              onChanged: (_) => setState(() {}),
            ),
          ] else if (_estado == EstadoBiblioteca.completado &&
              total != null) ...[
            const SizedBox(height: 16),
            Text(
              'Se guardará como episodio $total de $total.',
              style: textTheme.bodyMedium,
            ),
          ] else if (_estado == EstadoBiblioteca.pendiente) ...[
            const SizedBox(height: 16),
            Text(
              'Empezará en el episodio 0.',
              style: textTheme.bodyMedium,
            ),
          ],
          const SizedBox(height: 16),
          Text('Calificación (opcional)', style: textTheme.titleSmall),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: DropdownButtonFormField<int?>(
                  initialValue: _calificacion,
                  decoration: const InputDecoration(
                    border: OutlineInputBorder(),
                  ),
                  items: [
                    const DropdownMenuItem<int?>(
                      value: null,
                      child: Text('Sin calificación'),
                    ),
                    ...List.generate(
                      10,
                      (i) => DropdownMenuItem<int?>(
                        value: i + 1,
                        child: Text('${i + 1}'),
                      ),
                    ),
                  ],
                  onChanged: (valor) => setState(() {
                    _calificacion = valor;
                  }),
                ),
              ),
              if (_calificacion != null) ...[
                const SizedBox(width: 8),
                TextButton(
                  onPressed: () => setState(() {
                    _calificacion = null;
                  }),
                  child: const Text('Saltear'),
                ),
              ],
            ],
          ),
          const SizedBox(height: 24),
          Row(
            children: [
              if (widget.onQuitar != null)
                TextButton.icon(
                  onPressed: widget.onQuitar,
                  icon: const Icon(Icons.delete_outline),
                  label: const Text('Quitar'),
                ),
              const Spacer(),
              TextButton(
                onPressed: widget.onCancelar,
                child: const Text('Cancelar'),
              ),
              const SizedBox(width: 8),
              FilledButton(
                onPressed:
                    _puedeGuardar ? () => widget.onGuardar(
                          _construirEntrada(),
                        ) : null,
                child: const Text('Guardar'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

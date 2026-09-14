import 'package:anime_tracker/models/anime.dart';
import 'package:anime_tracker/models/entrada_biblioteca.dart';
import 'package:anime_tracker/widgets/modal_agregar_biblioteca.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// Tests del [ModalAgregarBiblioteca] (puro, sin repositorio ni red:
/// se bombean los callbacks y se capturan los valores).
void main() {
  const conTotal = Anime(
    id: 21,
    tituloRomaji: 'Con Total',
    episodios: 12,
    status: 'FINISHED',
  );
  const enEmision = Anime(
    id: 22,
    tituloRomaji: 'En Emision',
    episodios: null,
    proximoEpisodio: 8,
    status: 'RELEASING',
  );

  Future<void> bombearModal(
    WidgetTester tester, {
    required Anime anime,
    EntradaBiblioteca? existente,
    required ValueChanged<EntradaBiblioteca> onGuardar,
    VoidCallback? onQuitar,
  }) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ModalAgregarBiblioteca(
            anime: anime,
            entradaExistente: existente,
            onGuardar: onGuardar,
            onCancelar: () {},
            onQuitar: onQuitar,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
  }

  FilledButton botonGuardar(WidgetTester tester) {
    final boton = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, 'Guardar'),
    );
    return boton;
  }

  testWidgets('modo agregar: Guardar deshabilitado sin estado y sin Quitar',
      (tester) async {
    EntradaBiblioteca? guardada;
    await bombearModal(
      tester,
      anime: conTotal,
      onGuardar: (e) => guardada = e,
    );

    expect(find.text('Agregar a mi biblioteca'), findsOneWidget);
    expect(find.text('Quitar'), findsNothing);
    expect(botonGuardar(tester).onPressed, isNull);
    expect(guardada, isNull);
  });

  testWidgets('Viendo pide episodio válido y lo guarda', (tester) async {
    EntradaBiblioteca? guardada;
    await bombearModal(
      tester,
      anime: conTotal,
      onGuardar: (e) => guardada = e,
    );

    await tester.tap(find.text('Viendo'));
    await tester.pumpAndSettle();

    // Campo visible pero vacío: sigue deshabilitado.
    expect(find.text('Episodio actual'), findsOneWidget);
    expect(botonGuardar(tester).onPressed, isNull);

    // Mayor al total: error inline y sigue deshabilitado.
    await tester.enterText(find.byType(TextField), '99');
    await tester.pumpAndSettle();
    expect(find.text('No puede ser mayor al total (12).'), findsOneWidget);
    expect(botonGuardar(tester).onPressed, isNull);

    // Válido: habilita y guarda.
    await tester.enterText(find.byType(TextField), '3');
    await tester.pumpAndSettle();
    expect(find.text('No puede ser mayor al total (12).'), findsNothing);
    expect(botonGuardar(tester).onPressed, isNotNull);

    await tester.tap(find.text('Guardar'));
    await tester.pumpAndSettle();

    expect(guardada, isNotNull);
    expect(guardada!.estado, EstadoBiblioteca.viendo);
    expect(guardada!.episodioActual, 3);
    expect(guardada!.episodiosTotales, 12);
    expect(guardada!.calificacionPersonal, isNull);
  });

  testWidgets('episodio negativo muestra error y bloquea', (tester) async {
    await bombearModal(
      tester,
      anime: conTotal,
      onGuardar: (_) {},
    );

    await tester.tap(find.text('Abandonado'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField), '-1');
    await tester.pumpAndSettle();

    expect(find.text('El episodio no puede ser negativo.'), findsOneWidget);
    expect(botonGuardar(tester).onPressed, isNull);
  });

  testWidgets('Completado autocompleta con el total', (tester) async {
    EntradaBiblioteca? guardada;
    await bombearModal(
      tester,
      anime: conTotal,
      onGuardar: (e) => guardada = e,
    );

    await tester.tap(find.text('Completado'));
    await tester.pumpAndSettle();

    expect(find.text('Episodio actual'), findsNothing);
    expect(
      find.text('Se guardará como episodio 12 de 12.'),
      findsOneWidget,
    );
    expect(botonGuardar(tester).onPressed, isNotNull);

    await tester.tap(find.text('Guardar'));
    await tester.pumpAndSettle();

    expect(guardada!.estado, EstadoBiblioteca.completado);
    expect(guardada!.episodioActual, 12);
  });

  testWidgets('Completado deshabilitado sin total conocido', (tester) async {
    await bombearModal(
      tester,
      anime: enEmision,
      onGuardar: (_) {},
    );

    expect(
      find.text(
        'Completado no disponible: total desconocido (en emisión).',
      ),
      findsOneWidget,
    );

    // El segmento existe pero está deshabilitado: tocarlo no selecciona.
    await tester.tap(find.text('Completado'));
    await tester.pumpAndSettle();
    expect(botonGuardar(tester).onPressed, isNull);
    expect(find.text('Episodio actual'), findsNothing);
  });

  testWidgets('Pendiente fija el episodio en 0 sin campo', (tester) async {
    EntradaBiblioteca? guardada;
    await bombearModal(
      tester,
      anime: conTotal,
      onGuardar: (e) => guardada = e,
    );

    await tester.tap(find.text('Pendiente'));
    await tester.pumpAndSettle();

    expect(find.text('Episodio actual'), findsNothing);
    expect(find.text('Empezará en el episodio 0.'), findsOneWidget);
    expect(botonGuardar(tester).onPressed, isNotNull);

    await tester.tap(find.text('Guardar'));
    await tester.pumpAndSettle();

    expect(guardada!.estado, EstadoBiblioteca.pendiente);
    expect(guardada!.episodioActual, 0);
  });

  testWidgets('calificación opcional: se guarda y se puede saltear',
      (tester) async {
    EntradaBiblioteca? guardada;
    await bombearModal(
      tester,
      anime: conTotal,
      onGuardar: (e) => guardada = e,
    );

    await tester.tap(find.text('Pendiente'));
    await tester.pumpAndSettle();

    // Elegir 8 en el dropdown.
    await tester.tap(find.byType(DropdownButtonFormField<int?>));
    await tester.pumpAndSettle();
    await tester.tap(find.text('8').last);
    await tester.pumpAndSettle();

    await tester.tap(find.text('Guardar'));
    await tester.pumpAndSettle();
    expect(guardada!.calificacionPersonal, 8);

    // Saltearla la deja en null.
    guardada = null;
    await tester.tap(find.text('Saltear'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Guardar'));
    await tester.pumpAndSettle();
    expect(guardada!.calificacionPersonal, isNull);
  });

  testWidgets('modo edición: pre-carga valores y conserva fecha de alta',
      (tester) async {
    final alta = DateTime(2024, 5, 1);
    final existente = EntradaBiblioteca(
      animeId: conTotal.id,
      tituloAnime: 'Con Total',
      estado: EstadoBiblioteca.viendo,
      episodioActual: 5,
      episodiosTotales: 12,
      fechaAgregado: alta,
      calificacionPersonal: 9,
    );
    EntradaBiblioteca? guardada;
    var quito = false;
    await bombearModal(
      tester,
      anime: conTotal,
      existente: existente,
      onGuardar: (e) => guardada = e,
      onQuitar: () => quito = true,
    );

    expect(find.text('Editar en mi biblioteca'), findsOneWidget);
    expect(find.text('Quitar'), findsOneWidget);
    // Pre-cargado: episodio 5 y Guardar habilitado de entrada.
    expect(find.text('Episodio actual'), findsOneWidget);
    expect(
      tester.widget<TextField>(find.byType(TextField)).controller!.text,
      '5',
    );
    expect(botonGuardar(tester).onPressed, isNotNull);

    await tester.tap(find.text('Guardar'));
    await tester.pumpAndSettle();

    expect(guardada!.estado, EstadoBiblioteca.viendo);
    expect(guardada!.episodioActual, 5);
    expect(guardada!.calificacionPersonal, 9);
    expect(guardada!.fechaAgregado, alta);
    expect(quito, isFalse);

    await tester.tap(find.text('Quitar'));
    await tester.pumpAndSettle();
    expect(quito, isTrue);
  });

  testWidgets('edición inconsistente bloquea hasta corregir', (tester) async {
    await bombearModal(
      tester,
      anime: conTotal,
      existente: EntradaBiblioteca(
        animeId: conTotal.id,
        tituloAnime: 'Con Total',
        estado: EstadoBiblioteca.viendo,
        episodioActual: 20,
        episodiosTotales: 12,
      ),
      onGuardar: (_) {},
      onQuitar: () {},
    );

    expect(find.text('No puede ser mayor al total (12).'), findsOneWidget);
    expect(botonGuardar(tester).onPressed, isNull);

    await tester.enterText(find.byType(TextField), '10');
    await tester.pumpAndSettle();
    expect(botonGuardar(tester).onPressed, isNotNull);
  });
}

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# 1. INGRESO
st.set_page_config(page_title="Reporte Dispersión - SAP B4P", layout="wide")

# -------------------------------------------------------------
# CONTROL DE ACCESO (AUTENTICACIÓN)
# -------------------------------------------------------------
USUARIOS_AUTORIZADOS = {
    "inv_equipo": "B4P2026*",      # Usuario general para el equipo
    "owner": "SUB8RBI4B4P"         # Tu clave de administrador
}

# Inicializar variables de sesión si no existen
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
if "usuario_actual" not in st.session_state:
    st.session_state["usuario_actual"] = ""

# Si NO está autenticado, mostramos la pantalla de login y DETENEMOS el código
if not st.session_state["autenticado"]:
    st.markdown("<h2 style='text-align: center;'> Acceso Restringido - SAP B4P</h2>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.info("Ingresa tus credenciales para acceder al Dashboard de Inventario.")
        usuario_input = st.text_input("Usuario")
        password_input = st.text_input("Contraseña", type="password")

        if st.button("Iniciar Sesión", use_container_width=True):
            if usuario_input in USUARIOS_AUTORIZADOS and USUARIOS_AUTORIZADOS[usuario_input] == password_input:
                st.session_state["autenticado"] = True
                st.session_state["usuario_actual"] = usuario_input
                st.rerun()  # Recarga la página ya con acceso
            else:
                st.error(" Usuario o contraseña incorrectos.")

    # CRUCIAL: Detiene la ejecución aquí para que no se muestre el dashboard abajo
    st.stop()

# -------------------------------------------------------------
# PROTECCION DE INICIÓ SESIÓN
# -------------------------------------------------------------

# Botón para cerrar sesión en la barra lateral
st.sidebar.caption(f" Usuario: **{st.session_state['usuario_actual']}**")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state["autenticado"] = False
    st.session_state["usuario_actual"] = ""
    st.rerun()

@st.cache_data
def cargar_y_limpiar_datos_viva_piñata():
    df = pd.read_csv('BDS3.csv.gz', compression='gzip')

    # Detección por posición fija de columnas
    col_grupo = df.columns[0]        # Columna A: Grupo Artículo
    col_prenda = df.columns[1]       # Columna B: Nombre de la Prenda
    col_cod_seccion = df.columns[2]  # Columna C: Sección
    col_seccion = df.columns[3]      # Columna D: Nombre Seccion
    col_centro = df.columns[4]       # Columna E: Centro
    col_tienda = df.columns[5]       # Columna F: Nombre de la Tienda
    col_marca = df.columns[6]        # Columna G: Marca
    col_inv = df.columns[7]          # Columna H: Inv. Actual

    # Detección dinámica de métricas 2025 / 2026 y auxiliares
    metricas_deseadas = ['Venta 3M2026', 'Venta 3M2025', 'MOS 2026', 'MOS 2025', 'COBERTURA 2025', '% v']
    cols_encontradas = {}

    for target in metricas_deseadas:
        for c in df.columns:
            if target.lower() in str(c).lower().strip():
                cols_encontradas[target] = c
                break

    # Limpieza y estandarización de Secciones
    cod_str = df[col_cod_seccion].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    nom_str = df[col_seccion].astype(str).str.strip()
    df['Seccion_Label'] = cod_str + " - " + nom_str

    # Limpieza de Centro y Marca
    df[col_centro] = df[col_centro].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    df[col_marca] = df[col_marca].astype(str).str.strip()

    # Convertir métricas numéricas
    cols_numericas = [col_inv] + list(cols_encontradas.values())
    for col in cols_numericas:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Filtro numérico del inventario: Inv. Actual > 0
    df = df[df[col_inv] > 0]

    return df, col_grupo, col_prenda, col_cod_seccion, col_seccion, col_centro, col_tienda, col_marca, col_inv, cols_encontradas

# --- CARGA DE DATOS ---
df_base, col_grupo, col_prenda, col_cod_seccion, col_seccion, col_centro, col_tienda, col_marca, col_inv, cols_extra = cargar_y_limpiar_datos_viva_piñata()

# -------------------------------------------------------------
# APLICACIÓN DE SIDEBAR - FILTROS DE CONTROL
# -------------------------------------------------------------
st.sidebar.markdown("### Filtros de Control")

# 1. Sección
secciones_unicas = sorted([s for s in df_base['Seccion_Label'].dropna().unique() if str(s).lower() != 'nan'])
seccion_sel = st.sidebar.selectbox("Sección", ["Todas"] + secciones_unicas)

df_filtrado = df_base.copy()
if seccion_sel != "Todas":
    df_filtrado = df_filtrado[df_filtrado['Seccion_Label'] == seccion_sel]

# 2. Grupo Artículos
df_grupo_sum = df_filtrado.groupby(col_grupo)[col_inv].sum().reset_index()
df_grupo_sum = df_grupo_sum.sort_values(by=col_inv, ascending=False)
opciones_grupo = [f"{row[col_grupo]} ({row[col_inv]:,.0f})" for _, row in df_grupo_sum.iterrows()]
mapa_grupo = dict(zip(opciones_grupo, df_grupo_sum[col_grupo]))

grupos_sel = st.sidebar.multiselect("Grupo Artículos | Inv. Actual", options=opciones_grupo, default=[])
if grupos_sel:
    grupos_limpios = [mapa_grupo[g] for g in grupos_sel]
    df_filtrado = df_filtrado[df_filtrado[col_grupo].isin(grupos_limpios)]

# 3. Prenda
prendas_unicas = sorted([p for p in df_filtrado[col_prenda].dropna().astype(str).unique() if p.lower() != 'nan'])
prendas_sel = st.sidebar.multiselect("Prenda", prendas_unicas, default=[])
if prendas_sel:
    df_filtrado = df_filtrado[df_filtrado[col_prenda].astype(str).isin(prendas_sel)]

# 4. Centro
centros_unicos = sorted([c for c in df_filtrado[col_centro].dropna().astype(str).unique() if c.lower() != 'nan'])
centros_sel = st.sidebar.multiselect("Centro", centros_unicos, default=[])
if centros_sel:
    df_filtrado = df_filtrado[df_filtrado[col_centro].astype(str).isin(centros_sel)]

# 5. Tienda
tiendas_unicas = sorted([t for t in df_filtrado[col_tienda].dropna().astype(str).unique() if t.lower() != 'nan'])
tiendas_sel = st.sidebar.multiselect("Tienda", tiendas_unicas, default=[])
if tiendas_sel:
    df_filtrado = df_filtrado[df_filtrado[col_tienda].astype(str).isin(tiendas_sel)]

# 6. Marca
marcas_unicas = sorted([m for m in df_filtrado[col_marca].dropna().astype(str).unique() if m.lower() != 'nan'])
marcas_sel = st.sidebar.multiselect("Marca", marcas_unicas, default=[])
if marcas_sel:
    df_filtrado = df_filtrado[df_filtrado[col_marca].astype(str).isin(marcas_sel)]

# -------------------------------------------------------------
# DASHBOARD PRINCIPAL
# -------------------------------------------------------------
st.title(" Reporte Dispersión - SAP B4P")

# KPIs principales
m1, m2, m3 = st.columns(3)
m1.metric("Registros Filtrados (Inv > 0)", f"{len(df_filtrado):,}")
m2.metric("Inventario Actual Total", f"{df_filtrado[col_inv].sum():,.0f}")
m3.metric("Tiendas Activas en el Reporte", f"{df_filtrado[col_tienda].nunique():,}")

st.markdown("---")

if not df_filtrado.empty:
    st.subheader("Comparativo Métricas 2025 vs 2026")

    col_v26 = cols_extra.get('Venta 3M2026')
    col_v25 = cols_extra.get('Venta 3M2025')

    g1, g2 = st.columns(2)

    with g1:
        if col_v26 and col_v25:
            df_comp = df_filtrado.groupby(col_marca)[[col_v25, col_v26]].sum().reset_index()
            df_comp = df_comp.sort_values(by=col_v26, ascending=False).head(10)
            df_melt = df_comp.melt(id_vars=[col_marca], value_vars=[col_v25, col_v26], 
                                   var_name="Año / Métrica", value_name="Ventas 3M")

            fig_comp = px.bar(
                df_melt,
                x=col_marca,
                y="Ventas 3M",
                color="Año / Métrica",
                barmode="group",
                title="Ventas 3M por Marca (2025 vs 2026)",
                labels={col_marca: "Marca"},
                color_discrete_map={col_v25: '#636EFA', col_v26: '#00CC96'}
            )
            st.plotly_chart(fig_comp, use_container_width=True)
        else:
            st.info("Columnas de Venta 3M no encontradas para el gráfico comparativo.")

    with g2:
        top_prendas = df_filtrado.groupby(col_prenda)[col_inv].sum().reset_index()
        top_prendas = top_prendas.sort_values(by=col_inv, ascending=False).head(10)

        fig_dona = px.pie(
            top_prendas, 
            names=col_prenda, 
            values=col_inv, 
            hole=0.4,
            title="Distribución Top 10 Prendas por Inv. Actual",
            color_discrete_sequence=px.colors.sequential.Blues_r
        )
        st.plotly_chart(fig_dona, use_container_width=True)

    st.markdown("---")

    columnas_agrupar = [col_centro, col_tienda, col_marca, 'Seccion_Label']

    metricas_tabla = [col_inv]
    for key in ['Venta 3M2026', 'Venta 3M2025', 'MOS 2026', 'MOS 2025', 'COBERTURA 2025', '% v']:
        if key in cols_extra:
            metricas_tabla.append(cols_extra[key])

    tabla_pivot = df_filtrado.groupby(columnas_agrupar)[metricas_tabla].sum().reset_index()
    tabla_pivot = tabla_pivot.sort_values(by=col_inv, ascending=False)

    st.subheader(" Tabla Destacada (Top 15 Detallado con Métricas 2025/2026)")

    formato_dict = {col_inv: "{:,.0f}"}
    for m in metricas_tabla:
        if 'mos' in str(m).lower() or 'cobertura' in str(m).lower() or '% v' in str(m).lower():
            formato_dict[m] = "{:,.2f}"
        elif m != col_inv:
            formato_dict[m] = "{:,.0f}"

    styled_top15 = tabla_pivot.head(15).style.background_gradient(
        cmap="Blues", 
        subset=[col_inv]
    ).format(formato_dict)

    st.dataframe(styled_top15, use_container_width=True)

    with st.expander(" Despliegue de Tabla Completa con Todos los Registros"):
        styled_completa = tabla_pivot.style.background_gradient(
            cmap="Blues", 
            subset=[col_inv]
        ).format(formato_dict)
        st.dataframe(styled_completa, use_container_width=True, height=500)

    st.markdown("---")

    st.subheader("Análisis de Correlación: Venta 3M 2026 vs Inventario Actual")

    if col_v26:
        df_corr = df_filtrado.groupby([col_centro, col_tienda])[[col_v26, col_inv]].sum().reset_index()

        if len(df_corr) > 1:
            correlacion = df_corr[col_v26].corr(df_corr[col_inv])

            c_kpi, c_chart = st.columns([1, 2])

            with c_kpi:
                st.markdown("### Coeficiente")
                st.metric(
                    label="Correlación Pearson (r)", 
                    value=f"{correlacion:.4f}",
                    help="Un valor cercano a 1 indica que donde más se vende es donde más inventario hay."
                )

                if correlacion >= 0.7:
                    st.success("🟢 **Alta Alineación:** El inventario está correctamente distribuido en las tiendas de mayor venta.")
                elif correlacion >= 0.3:
                    st.warning("🟡 **Alineación Moderada:** Existen algunas oportunidades para balancear inventario entre tiendas.")
                elif correlacion >= 0:
                    st.error("🔴 **Baja Alineación:** El inventario no está respondiendo al nivel de ventas de las tiendas.")
                else:
                    st.error("⚠️ **Correlación Inversa:** Las tiendas con más inventario tienen menos ventas.")

                st.caption(f"Calculado sobre **{len(df_corr)}** combinaciones de Tienda/Centro según los filtros actuales.")

            with c_chart:
                fig_scatter = px.scatter(
                    df_corr,
                    x=col_v26,
                    y=col_inv,
                    hover_data=[col_tienda],
                    trendline="ols",
                    title="Dispersión por Tienda: Ventas 3M2026 vs Inv. Actual",
                    labels={col_v26: "Venta 3M2026", col_inv: "Inv. Actual"},
                    color_discrete_sequence=['#1f77b4']
                )
                st.plotly_chart(fig_scatter, use_container_width=True)
        else:
            st.info("Se necesitan al menos 2 registros/tiendas distintas con los filtros seleccionados para calcular la correlación.")
    else:
        st.info("No se encontró la columna 'Venta 3M2026' para calcular la correlación.")

else:
    st.warning("No hay datos que cumplan con los filtros seleccionados o con Inv. Actual > 0.")

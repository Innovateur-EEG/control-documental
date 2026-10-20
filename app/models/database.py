import os
import datetime
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime, Table, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from dotenv import load_dotenv, dotenv_values
from supabase import create_client, Client
import streamlit as st
from contextlib import contextmanager

load_dotenv()

Base = declarative_base()

# ==========================================
# TABLAS DE RELACIÓN Y ASOCIACIÓN
# ==========================================
usuario_proyecto_admin = Table(
    'usuario_proyecto_admin', Base.metadata,
    Column('usuario_id', Integer, ForeignKey('usuarios.id'), primary_key=True),
    Column('proyecto_id', Integer, ForeignKey('proyectos.id'), primary_key=True)
)

# FIX CRÍTICO: Objeto de Asociación en lugar de Tabla Simple para manejar permisos atómicos
class UsuarioPersonaGestor(Base):
    __tablename__ = 'usuario_persona_gestor'
    usuario_id = Column(Integer, ForeignKey('usuarios.id'), primary_key=True)
    persona_id = Column(Integer, ForeignKey('personas.id'), primary_key=True)
    # Fail-closed security: Por defecto es Solo Lectura
    nivel_permiso = Column(String, nullable=False, default="Solo Lectura") 
    
    usuario = relationship("Usuario", back_populates="personas_asignadas")
    persona = relationship("Persona", back_populates="usuarios_asignados")


# ==========================================
# PILAR 1: IDENTIDAD Y ACCESO
# ==========================================
class Usuario(Base):
    __tablename__ = 'usuarios'
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    nombre = Column(String, nullable=True)
    password_hash = Column(String, nullable=True) 
    telefono = Column(String, nullable=True)
    tipo_usuario = Column(String, nullable=False) 
    debe_cambiar_password = Column(Integer, default=1) 
    
    proyectos_admin = relationship("Proyecto", secondary=usuario_proyecto_admin, back_populates="admins")
    personas_asignadas = relationship("UsuarioPersonaGestor", back_populates="usuario", cascade="all, delete-orphan")


# ==========================================
# PILAR 2: ENTIDADES UNIVERSALES
# ==========================================
class Catalogo(Base):
    __tablename__ = 'catalogos'
    id = Column(Integer, primary_key=True)
    categoria = Column(String, nullable=False) 
    valor = Column(String, nullable=False)     

class Proyecto(Base):
    __tablename__ = 'proyectos'
    id = Column(Integer, primary_key=True)
    nombre = Column(String, nullable=False)
    estatus_general = Column(String, default="Activo")
    # FIX: func.now() en lugar de datetime.now()
    fecha_creacion = Column(DateTime, server_default=func.now())

    admins = relationship("Usuario", secondary=usuario_proyecto_admin, back_populates="proyectos_admin")
    participaciones = relationship("Participacion", back_populates="proyecto")

class Persona(Base):
    __tablename__ = 'personas'
    id = Column(Integer, primary_key=True)
    tipo = Column(String, nullable=False) 
    rfc = Column(String, nullable=True)
    razon_social_nombre = Column(String, nullable=False)
    # FIX: default=dict en lugar de default={}
    datos_json = Column(JSON, default=dict) 

    usuarios_asignados = relationship("UsuarioPersonaGestor", back_populates="persona", cascade="all, delete-orphan")
    participaciones = relationship("Participacion", back_populates="persona")


# ==========================================
# PILAR 3: CONTEXTO, JERARQUÍA Y DOCUMENTOS
# ==========================================
class Participacion(Base):
    __tablename__ = 'participaciones'
    id = Column(Integer, primary_key=True)
    proyecto_id = Column(Integer, ForeignKey('proyectos.id'), nullable=False)
    persona_id = Column(Integer, ForeignKey('personas.id'), nullable=False)
    rol = Column(String, nullable=False) 

    proyecto = relationship("Proyecto", back_populates="participaciones")
    persona = relationship("Persona", back_populates="participaciones")
    documentos = relationship("DocumentoExpediente", back_populates="participacion")
    
    hijos = relationship("JerarquiaParticipacion", foreign_keys='JerarquiaParticipacion.padre_id', back_populates="padre")
    padres = relationship("JerarquiaParticipacion", foreign_keys='JerarquiaParticipacion.hijo_id', back_populates="hijo")

class JerarquiaParticipacion(Base):
    __tablename__ = 'jerarquia_participaciones'
    id = Column(Integer, primary_key=True)
    padre_id = Column(Integer, ForeignKey('participaciones.id'), nullable=False)
    hijo_id = Column(Integer, ForeignKey('participaciones.id'), nullable=False)
    tipo_relacion = Column(String, nullable=False) 

    padre = relationship("Participacion", foreign_keys=[padre_id], back_populates="hijos")
    hijo = relationship("Participacion", foreign_keys=[hijo_id], back_populates="padres")

class DocumentoExpediente(Base):
    __tablename__ = 'documentos_expediente'
    id = Column(Integer, primary_key=True)
    participacion_id = Column(Integer, ForeignKey('participaciones.id'), nullable=False)
    categoria_documento = Column(String, nullable=False) 
    tipo_documento = Column(String, nullable=False) 
    estatus = Column(String, default="No empezado") 
    tracking_guia = Column(String, nullable=True)
    metadata_json = Column(JSON, default=dict) 
    ruta_archivo = Column(String, nullable=True) 
    fecha_actualizacion = Column(DateTime, server_default=func.now(), onupdate=func.now())

    participacion = relationship("Participacion", back_populates="documentos")

# ==========================================
# PILAR 4: GESTOR DINÁMICO DE PLANTILLAS Y CAMPOS
# ==========================================
class PlantillaFormato(Base):
    __tablename__ = 'plantillas_formato'
    id = Column(Integer, primary_key=True)
    nombre = Column(String, nullable=False)
    roles_aplica = Column(JSON, default=list) 
    paginas_totales = Column(Integer, nullable=False, default=1)
    rubricar_todas = Column(String, default="✅ Sí")
    firmas_json = Column(JSON, default=list) 
    ruta_plantilla_word = Column(String, nullable=True)

class ConfiguracionCampos(Base):
    __tablename__ = 'configuracion_campos'
    id = Column(Integer, primary_key=True)
    nombre_mostrar = Column(String, nullable=False)  
    llave_jinja = Column(String, nullable=False)     
    tipo_input = Column(String, nullable=False)      
    opciones_json = Column(JSON, default=list)         
    tipo_persona = Column(String, nullable=False)    
    roles_aplica = Column(JSON, default=list)          
    regla_validacion = Column(String, nullable=True) 
    configuracion_json = Column(JSON, nullable=False, default=dict)

class ConfiguracionEvidencia(Base):
    __tablename__ = 'configuracion_evidencias'
    id = Column(Integer, primary_key=True)
    nombre_evidencia = Column(String, nullable=False) 
    tipo_persona = Column(String, nullable=False)     
    roles_aplica = Column(JSON, default=list)
    configuracion_json = Column(JSON, nullable=False, default=dict)           

# ==========================================
# CONFIGURACIÓN SEGURA (CACHEADA Y SCOPEADA)
# ==========================================
@st.cache_resource
def get_engine():
    """Crea y cachea el motor de BD para evitar fugas de conexión y latencia"""
    DATABASE_URL = os.getenv("DATABASE_URL")
    secrets = dotenv_values(".secret")
    if not DATABASE_URL:
        DATABASE_URL = secrets.get("DATABASE_URL")
    
    if not DATABASE_URL:
        # Falla ruidosa por seguridad (Review 3)
        raise ValueError("CRÍTICO: No se proporcionó DATABASE_URL. El sistema no usará SQLite como fallback en producción.")
        
    if "[PWD]" in DATABASE_URL:
        db_pwd = os.getenv("SUPABASE_PROD") or secrets.get("SUPABASE_PROD")
        DATABASE_URL = DATABASE_URL.replace("[PWD]", db_pwd)

    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        
    # pool_pre_ping evita el "MySQL has gone away" / Desconexiones
    return create_engine(DATABASE_URL, pool_pre_ping=True, echo=False)

@st.cache_resource
def get_supabase_client():
    SUPABASE_URL = os.getenv("SUPABASE_URL") or dotenv_values(".secret").get("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or dotenv_values(".secret").get("SUPABASE_SERVICE_KEY")
    if SUPABASE_URL and SUPABASE_KEY:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    return None

engine = get_engine()
supabase_client = get_supabase_client()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@contextmanager
def db_session_scope():
    """Manejador de contexto para asegurar que la BD SIEMPRE se cierre"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def get_db_session():
    """Genera y retorna una sesión de base de datos activa."""
    return SessionLocal()

def init_db():
    Base.metadata.create_all(bind=engine)
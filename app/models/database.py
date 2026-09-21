import os
import datetime
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime, Table, JSON
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from dotenv import load_dotenv, dotenv_values

# Cargar variables de entorno (lee el .env local)
load_dotenv()

Base = declarative_base()

# ==========================================
# TABLAS DE RELACIÓN (MUCHOS A MUCHOS)
# ==========================================
usuario_proyecto_admin = Table(
    'usuario_proyecto_admin', Base.metadata,
    Column('usuario_id', Integer, ForeignKey('usuarios.id'), primary_key=True),
    Column('proyecto_id', Integer, ForeignKey('proyectos.id'), primary_key=True)
)

usuario_persona_gestor = Table(
    'usuario_persona_gestor', Base.metadata,
    Column('usuario_id', Integer, ForeignKey('usuarios.id'), primary_key=True),
    Column('persona_id', Integer, ForeignKey('personas.id'), primary_key=True)
)

# ==========================================
# PILAR 1: IDENTIDAD Y ACCESO
# ==========================================
class Usuario(Base):
    __tablename__ = 'usuarios'
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=True) # Permitimos null temporalmente para el OTP
    telefono = Column(String, nullable=True)
    tipo_usuario = Column(String, nullable=False) # 'SuperAdmin', 'Admin', 'Usuario'
    debe_cambiar_password = Column(Integer, default=1) # 1 = True, 0 = False (SQLite fallback compatible)
    
    # Relaciones de permisos
    proyectos_admin = relationship("Proyecto", secondary=usuario_proyecto_admin, back_populates="admins")
    personas_gestor = relationship("Persona", secondary=usuario_persona_gestor, back_populates="gestores")


# ==========================================
# PILAR 2: ENTIDADES UNIVERSALES
# ==========================================
class Catalogo(Base):
    """Almacena valores dinámicos para los selectores (dropdowns)"""
    __tablename__ = 'catalogos'
    id = Column(Integer, primary_key=True)
    categoria = Column(String, nullable=False) # Ej. 'Rol_Participacion', 'Tipo_Relacion'
    valor = Column(String, nullable=False)     # Ej. 'Fideicomisario', 'Representa a'
    
class Proyecto(Base):
    __tablename__ = 'proyectos'
    id = Column(Integer, primary_key=True)
    nombre = Column(String, nullable=False)
    estatus_general = Column(String, default="Activo")
    fecha_creacion = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))

    admins = relationship("Usuario", secondary=usuario_proyecto_admin, back_populates="proyectos_admin")
    participaciones = relationship("Participacion", back_populates="proyecto")

class Persona(Base):
    __tablename__ = 'personas'
    id = Column(Integer, primary_key=True)
    tipo = Column(String, nullable=False) # 'Fisica' o 'Moral'
    rfc = Column(String, nullable=True)
    razon_social_nombre = Column(String, nullable=False)
    datos_json = Column(JSON, default={}) # Domicilios, fechas, etc.

    gestores = relationship("Usuario", secondary=usuario_persona_gestor, back_populates="personas_gestor")
    participaciones = relationship("Participacion", back_populates="persona")


# ==========================================
# PILAR 3: CONTEXTO, JERARQUÍA Y DOCUMENTOS
# ==========================================
class Participacion(Base):
    """Vincula una Persona a un Proyecto con un Rol específico"""
    __tablename__ = 'participaciones'
    id = Column(Integer, primary_key=True)
    proyecto_id = Column(Integer, ForeignKey('proyectos.id'), nullable=False)
    persona_id = Column(Integer, ForeignKey('personas.id'), nullable=False)
    rol = Column(String, nullable=False) # Ej. 'Fideicomisario', 'Representante Legal'

    proyecto = relationship("Proyecto", back_populates="participaciones")
    persona = relationship("Persona", back_populates="participaciones")
    documentos = relationship("DocumentoExpediente", back_populates="participacion")
    
    # Relaciones para la jerarquía dinámica
    hijos = relationship("JerarquiaParticipacion", foreign_keys='JerarquiaParticipacion.padre_id', back_populates="padre")
    padres = relationship("JerarquiaParticipacion", foreign_keys='JerarquiaParticipacion.hijo_id', back_populates="hijo")


class JerarquiaParticipacion(Base):
    """Define quién representa o es socio de quién dentro de un Proyecto"""
    __tablename__ = 'jerarquia_participaciones'
    id = Column(Integer, primary_key=True)
    padre_id = Column(Integer, ForeignKey('participaciones.id'), nullable=False)
    hijo_id = Column(Integer, ForeignKey('participaciones.id'), nullable=False)
    tipo_relacion = Column(String, nullable=False) # 'Representa a', 'Es socio de'

    padre = relationship("Participacion", foreign_keys=[padre_id], back_populates="hijos")
    hijo = relationship("Participacion", foreign_keys=[hijo_id], back_populates="padres")


class DocumentoExpediente(Base):
    __tablename__ = 'documentos_expediente'
    id = Column(Integer, primary_key=True)
    participacion_id = Column(Integer, ForeignKey('participaciones.id'), nullable=False)
    categoria_documento = Column(String, nullable=False) # 'Formato_Sistema' o 'Evidencia_Adjunta'
    tipo_documento = Column(String, nullable=False) # Ej. 'Formato 1', 'INE', 'Comprobante Domicilio'
    estatus = Column(String, default="No empezado") 
    tracking_guia = Column(String, nullable=True)
    metadata_json = Column(JSON, default={}) # Vigencias, tipos de identificacion
    ruta_archivo = Column(String, nullable=True) # URL de Supabase Storage en el futuro
    fecha_actualizacion = Column(DateTime, default=datetime.datetime.now(datetime.timezone.utc), onupdate=datetime.datetime.now(datetime.timezone.utc))

    participacion = relationship("Participacion", back_populates="documentos")


# ==========================================
# CONFIGURACIÓN DE BASE DE DATOS
# ==========================================
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Inyección dinámica del password desde el archivo .secret
    if "[PWD]" in DATABASE_URL:
        # dotenv_values lee el archivo sin cargarlo al entorno global del SO
        secrets = dotenv_values(".secret")
        db_pwd = secrets.get("SUPABASE_PROD")
        
        if db_pwd:
            DATABASE_URL = DATABASE_URL.replace("[PWD]", db_pwd)
        else:
            raise ValueError("ERROR CRÍTICO: Se encontró PWD en DATABASE_URL pero no existe la contraseña en los secrets del entorno")

    # Adaptación para el formato de conexión de SQLAlchemy
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    print("CONNECTING TO SUPPABASE")    
    engine = create_engine(DATABASE_URL, echo=True)
else:
    # Fallback local
    print("CONNECTION ERROR. Fallback to local DB")
    engine = create_engine("sqlite:///app_database.sqlite3", echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
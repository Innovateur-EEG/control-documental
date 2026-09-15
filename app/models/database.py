import datetime
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, backref

Base = declarative_base()

class Proyecto(Base):
    __tablename__ = 'proyectos'
    id = Column(Integer, primary_key=True)
    nombre_proyecto = Column(String, nullable=False)
    fecha_creacion = Column(DateTime, default=datetime.datetime.utcnow)
    estatus_general = Column(String, default="Activo")

    participantes = relationship("Participante", back_populates="proyecto")

class Participante(Base):
    __tablename__ = 'participantes'
    id = Column(Integer, primary_key=True)
    proyecto_id = Column(Integer, ForeignKey('proyectos.id'))
    tipo_persona = Column(String)  # 'Fisica' o 'Moral'
    razon_social_o_nombre = Column(String, nullable=False)
    rfc = Column(String)
    id_padre = Column(Integer, ForeignKey('participantes.id'), nullable=True)
    rol_jerarquico = Column(String)  # 'Empresa', 'Representante', 'Apoderado', 'Relacionado'

    # Relaciones
    proyecto = relationship("Proyecto", back_populates="participantes")
    # Autoreferencia para la jerarquía (El padre es la Empresa, los hijos son sus relacionados)
    hijos = relationship("Participante", backref=backref('padre', remote_side=[id]))
    usuario = relationship("UsuarioAcceso", uselist=False, back_populates="participante")
    documentos = relationship("ExpedienteDocumento", back_populates="participante")

class UsuarioAcceso(Base):
    __tablename__ = 'usuarios_acceso'
    id = Column(Integer, primary_key=True)
    participante_id = Column(Integer, ForeignKey('participantes.id'))
    email = Column(String, unique=True, nullable=False)
    nivel_acceso = Column(String)  # 'Admin', 'Representante', 'Relacionado'

    participante = relationship("Participante", back_populates="usuario")

class ExpedienteDocumento(Base):
    __tablename__ = 'expedientes_documentos'
    id = Column(Integer, primary_key=True)
    participante_id = Column(Integer, ForeignKey('participantes.id'))
    tipo_documento = Column(String)  # Ej. 'Formato 1'
    estatus = Column(String, default="Pendiente")
    ruta_archivo = Column(String, nullable=True)
    fecha_modificacion = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    participante = relationship("Participante", back_populates="documentos")

# Configuración SQLite local (Preparado para cambiar a PostgreSQL mediante env vars después)
engine = create_engine("sqlite:///app_database.sqlite3", echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
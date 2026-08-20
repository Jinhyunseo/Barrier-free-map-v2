CREATE DATABASE IF NOT EXISTS barrier_free
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE barrier_free;

CREATE TABLE IF NOT EXISTS `user` (
  user_id INT NOT NULL AUTO_INCREMENT,
  email VARCHAR(255) NOT NULL,
  nickname VARCHAR(100) NOT NULL,
  password_hash VARCHAR(255) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id),
  UNIQUE KEY uq_user_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS transportation (
  transportation_id INT NOT NULL AUTO_INCREMENT,
  transport_type VARCHAR(30) NOT NULL,
  route_number VARCHAR(50) NULL,
  external_code VARCHAR(100) NULL,
  operator_name VARCHAR(150) NULL,
  is_low_floor BOOLEAN NULL,
  start_name VARCHAR(150) NULL,
  end_name VARCHAR(150) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (transportation_id),
  UNIQUE KEY uq_transportation_type_external (transport_type, external_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS facility (
  facility_id INT NOT NULL AUTO_INCREMENT,
  facility_type VARCHAR(30) NOT NULL,
  standard_name VARCHAR(200) NOT NULL,
  station_name VARCHAR(150) NULL,
  line_name VARCHAR(100) NULL,
  external_code VARCHAR(100) NULL,
  address VARCHAR(500) NULL,
  latitude DOUBLE NULL,
  longitude DOUBLE NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (facility_id),
  UNIQUE KEY uq_facility_type_external (facility_type, external_code),
  KEY ix_facility_standard_name (standard_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS facility_equipment (
  equipment_id INT NOT NULL AUTO_INCREMENT,
  facility_id INT NOT NULL,
  equipment_type VARCHAR(40) NOT NULL,
  external_equipment_no VARCHAR(100) NULL,
  exit_no VARCHAR(50) NULL,
  detail_location VARCHAR(1000) NULL,
  direction VARCHAR(50) NULL,
  from_floor VARCHAR(30) NULL,
  to_floor VARCHAR(30) NULL,
  capacity_persons INT NULL,
  capacity_kg INT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (equipment_id),
  UNIQUE KEY uq_equipment_facility_type_external_no (facility_id, equipment_type, external_equipment_no),
  KEY ix_equipment_facility_type (facility_id, equipment_type),
  CONSTRAINT fk_equipment_facility FOREIGN KEY (facility_id) REFERENCES facility(facility_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS facility_status (
  facility_status_id BIGINT NOT NULL AUTO_INCREMENT,
  facility_id INT NOT NULL,
  status_code VARCHAR(30) NOT NULL DEFAULT 'UNKNOWN',
  source VARCHAR(50) NOT NULL DEFAULT 'SEED',
  detail TEXT NULL,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (facility_status_id),
  KEY ix_facility_status_facility_updated (facility_id, updated_at),
  CONSTRAINT fk_facility_status_facility FOREIGN KEY (facility_id) REFERENCES facility(facility_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS equipment_status (
  equipment_status_id BIGINT NOT NULL AUTO_INCREMENT,
  equipment_id INT NOT NULL,
  status_code VARCHAR(30) NOT NULL DEFAULT 'UNKNOWN',
  source VARCHAR(50) NOT NULL DEFAULT 'SEED',
  detail TEXT NULL,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (equipment_status_id),
  KEY ix_equipment_status_equipment_updated (equipment_id, updated_at),
  CONSTRAINT fk_equipment_status_equipment FOREIGN KEY (equipment_id) REFERENCES facility_equipment(equipment_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS reports (
  report_id BIGINT NOT NULL AUTO_INCREMENT,
  user_id INT NOT NULL,
  facility_id INT NULL,
  equipment_id INT NULL,
  report_type VARCHAR(50) NOT NULL,
  title VARCHAR(255) NOT NULL,
  description TEXT NULL,
  location_text VARCHAR(500) NULL,
  captured_latitude DOUBLE NULL,
  captured_longitude DOUBLE NULL,
  image_url VARCHAR(500) NULL,
  report_status VARCHAR(30) NOT NULL DEFAULT 'RECEIVED',
  ai_verification VARCHAR(30) NOT NULL DEFAULT 'NOT_RUN',
  ai_confidence_score DOUBLE NULL,
  detected_status VARCHAR(30) NULL,
  reason TEXT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (report_id),
  KEY ix_reports_user_created (user_id, created_at),
  KEY ix_reports_facility_created (facility_id, created_at),
  KEY ix_reports_equipment_created (equipment_id, created_at),
  KEY ix_reports_status_created (report_status, created_at),
  CONSTRAINT fk_reports_user FOREIGN KEY (user_id) REFERENCES `user`(user_id),
  CONSTRAINT fk_reports_facility FOREIGN KEY (facility_id) REFERENCES facility(facility_id),
  CONSTRAINT fk_reports_equipment FOREIGN KEY (equipment_id) REFERENCES facility_equipment(equipment_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

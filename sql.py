ALTER TABLE users ADD COLUMN assigned_db VARCHAR(100) DEFAULT 'shpsk';


ALTER TABLE terms 
ADD COLUMN updated_at TIMESTAMP NULL DEFAULT NULL;

ALTER TABLE terms 
ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;


CREATE TABLE `fee_structure` (
    `fee_id` INT(11) NOT NULL AUTO_INCREMENT,
    `study_year_id` INT(11) NOT NULL,
    `term_id` INT(11) NOT NULL,
    `class_id` INT(11) NOT NULL, -- Changed to INT to link to your classes table
    `amount` DECIMAL(15, 2) NOT NULL,
    `category` ENUM('Tuition', 'Admission', 'Uniform', 'Transport', 'Other') DEFAULT 'Tuition',
    `date_updated` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`fee_id`),
    CONSTRAINT `fk_fee_year` FOREIGN KEY (`study_year_id`) REFERENCES `study_year` (`year_id`),
    CONSTRAINT `fk_fee_term` FOREIGN KEY (`term_id`) REFERENCES `terms` (`term_id`),
    INDEX (`class_id`, `term_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;




CREATE TABLE `payments` (
    `payment_id` INT(11) NOT NULL AUTO_INCREMENT,
    `ledger_id` INT(11) NOT NULL,
    `amount_received` DECIMAL(15, 2) NOT NULL,
    `payment_method` ENUM('Cash', 'Bank Transfer', 'Mobile Money', 'Cheque') DEFAULT 'Cash',
    `transaction_ref` VARCHAR(100) DEFAULT NULL, -- Bank slip number or M-Pesa ID
    `date_paid` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `received_by` INT(11) DEFAULT NULL, -- Link to your Users/Staff table
    `notes` TEXT DEFAULT NULL,
    PRIMARY KEY (`payment_id`),
    CONSTRAINT `fk_payment_ledger` FOREIGN KEY (`ledger_id`) REFERENCES `student_ledger` (`ledger_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;







CREATE TABLE `student_ledger` (
    `ledger_id` INT(11) NOT NULL AUTO_INCREMENT,
    `pupil_id` INT(11) NOT NULL,
    `study_year_id` INT(11) NOT NULL,
    `term_id` INT(11) NOT NULL,
    `amount_charged` DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
    `amount_paid` DECIMAL(15, 2) NOT NULL DEFAULT 0.00,
    /* Auto-calculates: Charged - Paid */
    `balance` DECIMAL(15, 2) GENERATED ALWAYS AS (`amount_charged` - `amount_paid`) VIRTUAL,
    `status` ENUM('Unpaid', 'Partial', 'Cleared') AS (
        CASE 
            WHEN `amount_paid` <= 0 THEN 'Unpaid'
            WHEN `amount_paid` < `amount_charged` THEN 'Partial'
            ELSE 'Cleared'
        END
    ) VIRTUAL,
    PRIMARY KEY (`ledger_id`),
    CONSTRAINT `fk_ledger_pupil` FOREIGN KEY (`pupil_id`) REFERENCES `pupils` (`pupil_id`) ON DELETE CASCADE,
    CONSTRAINT `fk_ledger_year` FOREIGN KEY (`study_year_id`) REFERENCES `study_year` (`year_id`),
    CONSTRAINT `fk_ledger_term` FOREIGN KEY (`term_id`) REFERENCES `terms` (`term_id`),
    INDEX (`status`),
    INDEX (`pupil_id`, `term_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;






ALTER TABLE `fee_structure` 
ADD UNIQUE INDEX `unique_fee_rule` (`study_year_id`, `term_id`, `class_id`, `category`);



CREATE TABLE application_fees (
    payment_id INT PRIMARY KEY AUTO_INCREMENT,
    admission_id INT NOT NULL,
    fee_id INT NOT NULL,
    payment_status ENUM('Unpaid','Paid') DEFAULT 'Unpaid',
    payment_reference VARCHAR(100),
    payment_date DATETIME NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (admission_id) REFERENCES admissions(admission_id) ON DELETE CASCADE,
    FOREIGN KEY (fee_id) REFERENCES fee_structure(fee_id)
);



ALTER TABLE admissions
ADD COLUMN form_id INT,
ADD CONSTRAINT fk_admission_form
FOREIGN KEY (form_id) REFERENCES application_fee(id);


✅ Add form_id (linked to application_fee table)
✅ Automatically fetch Admission fee from fee_structure
✅ Insert record into application_fee
✅ Link application_fee.id → admissions.form_id
✅ Keep everything inside ONE secure transaction



ALTER TABLE fee_structure
ADD CONSTRAINT unique_fee
UNIQUE (study_year_id, term_id, class_id, category);

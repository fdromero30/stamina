package com.stamina.usersconfig.user.dto;

import jakarta.validation.ConstraintViolation;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import jakarta.validation.ValidatorFactory;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestInstance;

import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class SimulateLoginRequestTest {

    private ValidatorFactory validatorFactory;
    private Validator validator;

    @BeforeAll
    void setUp() {
        try {
            validatorFactory = Validation.buildDefaultValidatorFactory();
            validator = validatorFactory.getValidator();
        } catch (Exception ex) {
            throw new IllegalStateException("No se pudo inicializar el validador de pruebas.", ex);
        }
    }

    @AfterAll
    void tearDown() {
        try {
            if (validatorFactory != null) {
                validatorFactory.close();
            }
        } catch (Exception ex) {
            throw new IllegalStateException("No se pudo cerrar el validador de pruebas.", ex);
        }
    }

    @Test
    void debeCrearRecordConEmailValido() {
        var request = new SimulateLoginRequest("usuario@stamina.test");
        assertThat(request.email()).isEqualTo("usuario@stamina.test");
    }

    @Test
    void debePasarValidacionConEmailValido() {
        var request = new SimulateLoginRequest("usuario@stamina.test");
        assertThat(validar(request)).isEmpty();
    }

    @Test
    void debePermitirEmailNulo() {
        var request = new SimulateLoginRequest(null);
        assertThat(validar(request)).isEmpty();
    }

    @Test
    void debeRechazarEmailInvalido() {
        var request = new SimulateLoginRequest("correo-invalido");

        assertThat(validar(request))
                .hasSize(1)
                .extracting(ConstraintViolation::getPropertyPath)
                .extracting(Object::toString)
                .containsExactly("email");
    }

    @Test
    void debePermitirEmailVacio() {
        // @Email sin @NotBlank permite cadena vacía; el servicio usa el email por defecto del seeder.
        var request = new SimulateLoginRequest("");
        assertThat(validar(request)).isEmpty();
    }

    @Test
    void recordsConMismoEmailDebenSerIguales() {
        var primera = new SimulateLoginRequest("usuario@stamina.test");
        var segunda = new SimulateLoginRequest("usuario@stamina.test");

        assertThat(primera).isEqualTo(segunda);
        assertThat(primera.hashCode()).isEqualTo(segunda.hashCode());
    }

    private Set<ConstraintViolation<SimulateLoginRequest>> validar(SimulateLoginRequest request) {
        try {
            return validator.validate(request);
        } catch (Exception ex) {
            throw new IllegalStateException("No se pudo validar la solicitud de simulación.", ex);
        }
    }
}

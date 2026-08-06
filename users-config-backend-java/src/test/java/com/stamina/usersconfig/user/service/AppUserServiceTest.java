package com.stamina.usersconfig.user.service;

import com.stamina.usersconfig.user.dto.CreateUserRequest;
import com.stamina.usersconfig.user.dto.LoginRequest;
import com.stamina.usersconfig.user.dto.UserResponse;
import com.stamina.usersconfig.user.entity.AppUser;
import com.stamina.usersconfig.user.exception.InvalidCredentialsException;
import com.stamina.usersconfig.user.exception.UserAlreadyExistsException;
import com.stamina.usersconfig.user.repository.AppUserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.crypto.password.PasswordEncoder;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class AppUserServiceTest {

    private static final String TEST_PASSWORD = "stamina123";
    private static final String HASHED_PASSWORD = "hashed-password";

    @Mock
    private AppUserRepository repository;

    @Mock
    private PasswordEncoder passwordEncoder;

    private AppUserService service;
    private AppUser alice;

    @BeforeEach
    void setUp() {
        service = new AppUserService(repository, passwordEncoder);
        alice = new AppUser("alice@stamina.local", "Alice", HASHED_PASSWORD);
        setUserId(alice, UUID.randomUUID());
    }

    @Test
    void simulateLogin_debeUsarEmailPorDefectoCuandoEsNulo() {
        try {
            when(repository.findByEmail("alice@stamina.local")).thenReturn(Optional.of(alice));
            when(passwordEncoder.matches(TEST_PASSWORD, HASHED_PASSWORD)).thenReturn(true);

            UserResponse response = service.simulateLogin(null);

            assertThat(response.email()).isEqualTo("alice@stamina.local");
            verify(repository).findByEmail("alice@stamina.local");
        } catch (Exception ex) {
            throw new AssertionError("Falló simulateLogin con email nulo.", ex);
        }
    }

    @Test
    void simulateLogin_debeNormalizarEmailIndicado() {
        try {
            when(repository.findByEmail("bob@stamina.local")).thenReturn(Optional.of(alice));
            when(passwordEncoder.matches(TEST_PASSWORD, HASHED_PASSWORD)).thenReturn(true);

            service.simulateLogin("  bob@stamina.local  ");

            verify(repository).findByEmail("bob@stamina.local");
        } catch (Exception ex) {
            throw new AssertionError("Falló simulateLogin con email con espacios.", ex);
        }
    }

    @Test
    void simulateLogin_debePropagarCredencialesInvalidas() {
        try {
            when(repository.findByEmail(anyString())).thenReturn(Optional.empty());

            assertThatThrownBy(() -> service.simulateLogin("desconocido@stamina.local"))
                    .isInstanceOf(InvalidCredentialsException.class);
        } catch (Exception ex) {
            throw new AssertionError("Falló la propagación de credenciales inválidas.", ex);
        }
    }

    @Test
    void simulateCreateUser_debeGenerarEmailUnicoCuandoEsNulo() {
        try {
            when(repository.existsByEmail(anyString())).thenReturn(false);
            when(passwordEncoder.encode(TEST_PASSWORD)).thenReturn(HASHED_PASSWORD);
            when(repository.save(any(AppUser.class))).thenAnswer(invocation -> invocation.getArgument(0));

            ArgumentCaptor<AppUser> userCaptor = ArgumentCaptor.forClass(AppUser.class);

            UserResponse response = service.simulateCreateUser(null, null);

            verify(repository).save(userCaptor.capture());
            AppUser saved = userCaptor.getValue();
            assertThat(saved.getEmail()).startsWith("test-").endsWith("@stamina.local");
            assertThat(saved.getDisplayName()).isEqualTo("Usuario de prueba");
            assertThat(response.email()).isEqualTo(saved.getEmail());
        } catch (Exception ex) {
            throw new AssertionError("Falló simulateCreateUser con valores nulos.", ex);
        }
    }

    @Test
    void simulateCreateUser_debePropagarEmailDuplicado() {
        try {
            when(repository.existsByEmail("carol@stamina.local")).thenReturn(true);

            assertThatThrownBy(() -> service.simulateCreateUser("carol@stamina.local", "Carol"))
                    .isInstanceOf(UserAlreadyExistsException.class);
        } catch (Exception ex) {
            throw new AssertionError("Falló la propagación de email duplicado.", ex);
        }
    }

    @Test
    void login_debeNormalizarEmailAntesDeBuscar() {
        try {
            when(repository.findByEmail("alice@stamina.local")).thenReturn(Optional.of(alice));
            when(passwordEncoder.matches(TEST_PASSWORD, HASHED_PASSWORD)).thenReturn(true);

            service.login(new LoginRequest("  alice@stamina.local  ", TEST_PASSWORD));

            verify(repository).findByEmail("alice@stamina.local");
        } catch (Exception ex) {
            throw new AssertionError("Falló la normalización de email en login.", ex);
        }
    }

    @Test
    void listAll_debeMapearEntidadesSinMaterializarColeccionesIntermedias() {
        try {
            when(repository.findAll()).thenReturn(List.of(alice));

            List<UserResponse> users = service.listAll();

            assertThat(users).hasSize(1);
            assertThat(users.getFirst().email()).isEqualTo("alice@stamina.local");
        } catch (Exception ex) {
            throw new AssertionError("Falló listAll.", ex);
        }
    }

    private static void setUserId(AppUser user, UUID id) {
        try {
            var idField = AppUser.class.getDeclaredField("id");
            idField.setAccessible(true);
            idField.set(user, id);
        } catch (Exception ex) {
            throw new IllegalStateException("No se pudo asignar el id de prueba.", ex);
        }
    }
}
